"""
Mathematical Engine: MAD/CUSUM anomaly detection and spike profiling.

Algorithm:
- Modified Z-Score using Median Absolute Deviation (MAD) for noise-robust detection.
- CUSUM (Cumulative Sum) for exact spike start/end boundary detection.
- Feature extraction: Rise Time, Integral (area under curve), Kurtosis.
"""
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from scipy import stats
from app.config import get_settings

settings = get_settings()


@dataclass
class AnomalySignal:
    """Result of MAD/CUSUM analysis on a metric time series."""
    is_anomaly: bool
    modified_z_score: float
    cusum_upper: float
    cusum_lower: float
    spike_start_idx: Optional[int] = None
    spike_end_idx: Optional[int] = None
    peak_value: float = 0.0
    rise_time_seconds: float = 0.0
    integral: float = 0.0
    kurtosis: float = 0.0
    mean_shift_direction: str = "none"  # up | down | none


@dataclass
class SpikeProfile:
    """Extracted features from a detected spike, used to build/match profiles."""
    peak_value: float
    duration_seconds: float
    rise_time_seconds: float
    integral: float
    kurtosis: float
    start_ts: float  # Unix timestamp
    end_ts: float    # Unix timestamp


def compute_mad_zscore(values: np.ndarray) -> np.ndarray:
    """
    Compute the modified Z-score for an array using MAD.
    Robust to outliers unlike standard Z-score.
    Formula: 0.6745 * (xi - median) / MAD
    """
    median = np.median(values)
    mad = np.median(np.abs(values - median))
    if mad == 0:
        # Avoid division by zero when all values are identical
        mad = np.finfo(float).eps
    return 0.6745 * (values - median) / mad


def run_cusum(
    values: np.ndarray,
    target_mean: Optional[float] = None,
    slack_multiplier: float = None,
    alarm_threshold: float = None,
) -> tuple[np.ndarray, np.ndarray, list[int], list[int]]:
    """
    CUSUM (Cumulative Sum) change-point detection.
    Returns upper/lower CUSUM arrays and alarm start/end indices.

    Parameters:
        values: Time series array.
        target_mean: Expected mean (μ₀). Defaults to median of values.
        slack_multiplier: k = slack_multiplier * sigma. Default: 0.5.
        alarm_threshold: H = alarm_threshold * sigma. Default: 4.0.
    """
    if slack_multiplier is None:
        slack_multiplier = settings.CUSUM_SLACK_MULTIPLIER
    if alarm_threshold is None:
        alarm_threshold = settings.CUSUM_ALARM_THRESHOLD

    if target_mean is None:
        target_mean = float(np.median(values))

    sigma = float(np.std(values))
    if sigma == 0:
        sigma = 1e-10

    k = slack_multiplier * sigma  # Allowable slack
    h = alarm_threshold * sigma   # Alarm threshold

    c_plus = np.zeros(len(values))
    c_minus = np.zeros(len(values))
    alarm_starts = []
    alarm_ends = []
    in_alarm = False

    for i in range(1, len(values)):
        c_plus[i] = max(0.0, c_plus[i - 1] + (values[i] - target_mean - k))
        c_minus[i] = max(0.0, c_minus[i - 1] - (values[i] - target_mean + k))

        currently_alarming = c_plus[i] > h or c_minus[i] > h

        if currently_alarming and not in_alarm:
            # Find where alarm actually started (backtrack to where CUSUM left 0)
            start = i
            while start > 0 and c_plus[start - 1] > 0:
                start -= 1
            alarm_starts.append(start)
            in_alarm = True
        elif not currently_alarming and in_alarm:
            alarm_ends.append(i)
            in_alarm = False

    if in_alarm:
        alarm_ends.append(len(values) - 1)

    return c_plus, c_minus, alarm_starts, alarm_ends


def detect_anomaly(
    timestamps: list[float],
    values: list[float],
    baseline_mean: Optional[float] = None,
    poll_interval_seconds: int = 30,
) -> AnomalySignal:
    """
    Main anomaly detection function.
    Combines MAD Z-score and CUSUM to detect and locate anomalies.

    Args:
        timestamps: Unix timestamps.
        values: Metric values (e.g., CPU%).
        baseline_mean: Historical mean from knowledge base. If None, uses data median.
        poll_interval_seconds: Time between samples in seconds.

    Returns:
        AnomalySignal with all detection results.
    """
    arr = np.array(values, dtype=float)

    if len(arr) < 5:
        return AnomalySignal(is_anomaly=False, modified_z_score=0.0, cusum_upper=0.0, cusum_lower=0.0)

    # --- MAD Z-Score ---
    z_scores = compute_mad_zscore(arr)
    max_z = float(np.max(np.abs(z_scores)))
    is_anomaly = max_z > settings.MAD_ZSCORE_THRESHOLD

    # --- CUSUM ---
    c_plus, c_minus, starts, ends = run_cusum(arr, target_mean=baseline_mean)
    spike_start_idx = starts[-1] if starts else None
    spike_end_idx = ends[-1] if ends else None

    if not is_anomaly and (starts and ends):
        is_anomaly = True  # CUSUM caught a mean shift even if MAD missed it

    direction = "none"
    if is_anomaly:
        direction = "up" if float(np.mean(arr[-5:])) > float(np.median(arr)) else "down"

    signal = AnomalySignal(
        is_anomaly=is_anomaly,
        modified_z_score=max_z,
        cusum_upper=float(c_plus[-1]),
        cusum_lower=float(c_minus[-1]),
        spike_start_idx=spike_start_idx,
        spike_end_idx=spike_end_idx,
        mean_shift_direction=direction,
    )

    if is_anomaly and spike_start_idx is not None:
        signal.peak_value = float(np.max(arr[spike_start_idx:]))

        # Rise time: indices from 10% to 90% of peak relative to baseline
        baseline = float(np.median(arr[:spike_start_idx]) if spike_start_idx > 0 else np.median(arr))
        amplitude = signal.peak_value - baseline
        if amplitude > 0:
            threshold_10 = baseline + 0.10 * amplitude
            threshold_90 = baseline + 0.90 * amplitude
            spike_segment = arr[spike_start_idx:]
            idx_10 = next((i for i, v in enumerate(spike_segment) if v >= threshold_10), 0)
            idx_90 = next((i for i, v in enumerate(spike_segment) if v >= threshold_90), idx_10)
            signal.rise_time_seconds = float((idx_90 - idx_10) * poll_interval_seconds)

        # Integral (area above baseline)
        if spike_end_idx is not None:
            spike_window = arr[spike_start_idx:spike_end_idx + 1]
        else:
            spike_window = arr[spike_start_idx:]
        signal.integral = float(np.sum(np.maximum(spike_window - baseline, 0)) * poll_interval_seconds)

        # Kurtosis of the spike shape
        if len(spike_window) >= 4:
            signal.kurtosis = float(stats.kurtosis(spike_window))

    return signal


def extract_spike_profile(
    timestamps: list[float],
    values: list[float],
    signal: AnomalySignal,
    poll_interval_seconds: int = 30,
) -> Optional[SpikeProfile]:
    """
    Extract a SpikeProfile from a resolved anomaly signal.
    Used to build the knowledge base.
    """
    if not signal.is_anomaly or signal.spike_start_idx is None:
        return None

    start_idx = signal.spike_start_idx
    end_idx = signal.spike_end_idx if signal.spike_end_idx is not None else len(timestamps) - 1

    duration_seconds = (end_idx - start_idx) * poll_interval_seconds

    return SpikeProfile(
        peak_value=signal.peak_value,
        duration_seconds=float(duration_seconds),
        rise_time_seconds=signal.rise_time_seconds,
        integral=signal.integral,
        kurtosis=signal.kurtosis,
        start_ts=timestamps[start_idx],
        end_ts=timestamps[min(end_idx, len(timestamps) - 1)],
    )


def matches_profile(signal: AnomalySignal, profile: dict, sigma_tolerance: float = 2.0) -> bool:
    """
    Compare a live anomaly signal against a stored MetricProfile.
    Returns True if the current spike's features are within `sigma_tolerance` of the profile.
    """
    if not signal.is_anomaly:
        return False

    # Check peak CPU within ±sigma_tolerance * std (use 20% tolerance if no std)
    peak_ok = abs(signal.peak_value - profile["mean_peak_cpu"]) < (profile["mean_peak_cpu"] * 0.30)

    # Check integral within tolerance
    if profile["mean_integral"] > 0:
        integral_ok = abs(signal.integral - profile["mean_integral"]) / profile["mean_integral"] < 0.50
    else:
        integral_ok = True

    return peak_ok and integral_ok


def build_or_update_profile(existing: Optional[dict], new_profile: SpikeProfile) -> dict:
    """
    Online averaging — incrementally update a profile with a new observation.
    Uses Welford's online algorithm for running mean.
    """
    if existing is None:
        return {
            "mean_peak_cpu": new_profile.peak_value,
            "mean_rise_time_seconds": new_profile.rise_time_seconds,
            "mean_integral": new_profile.integral,
            "expected_duration_minutes": new_profile.duration_seconds / 60.0,
            "std_duration_minutes": 0.0,
            "sample_count": 1,
        }

    n = existing["sample_count"] + 1
    prev_mean_duration = existing["expected_duration_minutes"]
    new_duration_min = new_profile.duration_seconds / 60.0

    # Welford online mean update
    delta = new_duration_min - prev_mean_duration
    new_mean_duration = prev_mean_duration + delta / n

    # Running variance (simplified)
    new_std = abs(existing["std_duration_minutes"] + delta * (new_duration_min - new_mean_duration))

    return {
        "mean_peak_cpu": (existing["mean_peak_cpu"] * (n - 1) + new_profile.peak_value) / n,
        "mean_rise_time_seconds": (existing["mean_rise_time_seconds"] * (n - 1) + new_profile.rise_time_seconds) / n,
        "mean_integral": (existing["mean_integral"] * (n - 1) + new_profile.integral) / n,
        "expected_duration_minutes": new_mean_duration,
        "std_duration_minutes": new_std,
        "sample_count": n,
    }
