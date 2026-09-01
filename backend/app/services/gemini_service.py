"""
Gemini Intelligence Service.

Implements:
- Streaming thinking mode (Gemini 3 Pro) for root cause analysis.
- Single-call approach: thinking blocks stream first, then structured JSON response.
- Separate fast classification via Gemini 3 Flash.

References:
  https://ai.google.dev/gemini-api/docs/text-generation
  https://ai.google.dev/gemini-api/docs/structured-output
  https://ai.google.dev/gemini-api/docs/thinking
"""
import json
import logging
from typing import AsyncIterator, Optional
from pathlib import Path

from google import genai
from google.genai import types

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Load system prompt from specs
_SYSTEM_PROMPT_PATH = Path(__file__).parent.parent.parent.parent / "specs" / "gemini_thinking_system_prompt.txt"
_DEFAULT_SYSTEM_PROMPT = """
ROLE: Senior Site Reliability Engineer (SRE) & Database Expert
IDENTITY: You are the core reasoning engine for "AIOps Sentinel".
TASK: Analyze infrastructure anomalies by correlating multi-modal data.

You MUST engage in a multi-step thinking process before providing the final JSON.
In your thinking block:
1. TEMPORAL ANALYSIS: Compare current_duration against expected_profile_duration.
2. SLOPE VALIDATION: Determine if CPU rise matches a Batch signature (sharp) or Anomaly (gradual/jittery).
3. LOG CORRELATION: Scan logs for database-specific errors (ORA-, FATAL, Deadlock, Connection Refused).
4. HYPOTHESIS GENERATION: Formulate at least two possible causes.
5. VERIFICATION: If metrics are high but logs are clean, flag as "Ambiguous/Unknown".

OUTPUT_CONSTRAINTS:
- RESPONSE_FORMAT: Strictly valid JSON as defined in the response_schema.
- TONE: Professional, terse, and objective.
- If data is insufficient, state root_cause_analysis as "Insufficient data for diagnostic".
- If Target is PROD, increase urgency in the output JSON.
"""


def _load_system_prompt() -> str:
    if _SYSTEM_PROMPT_PATH.exists():
        return _SYSTEM_PROMPT_PATH.read_text()
    return _DEFAULT_SYSTEM_PROMPT


def _build_analysis_prompt(context: dict) -> str:
    """
    Build the analysis prompt from incident context.
    Injects metrics, logs, history, and target info into structured sections.
    """
    target_info = context.get("target_info", {})
    metrics = context.get("metrics", {})
    logs = context.get("logs", "No logs available.")
    history = context.get("history", {})
    trigger_reason = context.get("trigger_reason", "Anomaly detected")

    return f"""
## INCIDENT ANALYSIS REQUEST

**Trigger**: {trigger_reason}

<TARGET_INFO>
Name: {target_info.get('name', 'Unknown')}
Environment: {target_info.get('environment', 'Unknown')}
Priority: {target_info.get('priority', 1)} ({'PROD' if target_info.get('environment') == 'prod' else 'NON-PROD'})
DB Type: {target_info.get('db_type', 'Unknown')}
</TARGET_INFO>

<METRICS>
{json.dumps(metrics, indent=2)}
</METRICS>

<HISTORY>
{json.dumps(history, indent=2) if history else "No historical profile found for this target. This appears to be a new/unknown event type."}
</HISTORY>

<LOGS>
{logs}
</LOGS>

Analyze the above data and provide your diagnosis in the required JSON format.
"""


class GeminiService:
    """
    Wraps the Google Gemini API for AIOps Sentinel intelligence layer.
    """

    def __init__(self):
        self._client: Optional[genai.Client] = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            if not settings.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY is not configured.")
            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._client

    async def stream_analysis(
        self,
        context: dict,
        thinking_budget: Optional[int] = None,
        system_prompt_override: Optional[str] = None,
        schema_override: Optional[dict] = None,
    ) -> AsyncIterator[dict]:
        """
        Stream a full analysis of an incident.

        Yields dicts of shape:
          {"type": "thought", "text": "..."}   — streaming thinking block
          {"type": "final", "data": {...}}      — structured JSON verdict
          {"type": "error", "text": "..."}      — on failure

        Uses a single Gemini call with:
          - include_thoughts=True  → streams thinking blocks
          - response_mime_type=application/json → ensures structured final output
        """
        client = self._get_client()
        budget = thinking_budget or settings.GEMINI_THINKING_BUDGET
        system_prompt = system_prompt_override or _load_system_prompt()
        response_schema = schema_override or settings.gemini_response_schema
        prompt = _build_analysis_prompt(context)

        json_buffer = ""

        try:
            async for chunk in await client.aio.models.generate_content_stream(
                model=settings.GEMINI_PRO_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    thinking_config=types.ThinkingConfig(
                        include_thoughts=True,
                        thinking_budget=budget,
                    ),
                    temperature=0.1,  # Low temperature for deterministic analysis
                ),
            ):
                if not chunk.candidates:
                    continue

                for part in chunk.candidates[0].content.parts:
                    if not part.text:
                        continue
                    # Thinking blocks have thought=True
                    if hasattr(part, "thought") and part.thought:
                        yield {"type": "thought", "text": part.text}
                    else:
                        # Accumulate structured JSON response
                        json_buffer += part.text

            # Parse and yield final structured output
            if json_buffer.strip():
                try:
                    structured = json.loads(json_buffer.strip())
                    yield {"type": "final", "data": structured}
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse Gemini structured output: {e}\nBuffer: {json_buffer[:500]}")
                    yield {"type": "error", "text": f"JSON parse error: {e}"}
            else:
                yield {"type": "error", "text": "No structured output received from Gemini."}

        except Exception as e:
            logger.error(f"Gemini streaming error: {e}", exc_info=True)
            yield {"type": "error", "text": str(e)}

    async def quick_classify(self, context: dict) -> Optional[dict]:
        """
        Fast classification using Gemini Flash (no thinking).
        Used for initial triage before deep analysis.
        Returns a partial result with just severity estimate.
        """
        client = self._get_client()
        prompt = _build_analysis_prompt(context)

        flash_schema = {
            "type": "object",
            "properties": {
                "is_anomaly": {"type": "boolean"},
                "severity": {"type": "string", "enum": ["INFO", "WARNING", "CRITICAL"]},
                "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
                "root_cause_analysis": {"type": "string"},
            },
            "required": ["is_anomaly", "severity", "confidence_score", "root_cause_analysis"],
        }

        try:
            response = await client.aio.models.generate_content(
                model=settings.GEMINI_FLASH_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_load_system_prompt(),
                    response_mime_type="application/json",
                    response_schema=flash_schema,
                    temperature=0.1,
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Gemini Flash classify error: {e}", exc_info=True)
            return None

    async def test_prompt(
        self,
        system_prompt: str,
        json_schema: dict,
        test_context: dict,
    ) -> dict:
        """
        Prompt Lab: test a custom prompt + schema against sample data.
        Returns both thinking process and final output.
        """
        client = self._get_client()
        prompt = _build_analysis_prompt(test_context)

        thought_buffer = ""
        json_buffer = ""

        async for chunk in await client.aio.models.generate_content_stream(
            model=settings.GEMINI_PRO_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=json_schema,
                thinking_config=types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=settings.GEMINI_THINKING_BUDGET_MEDIUM,
                ),
                temperature=0.1,
            ),
        ):
            if not chunk.candidates:
                continue
            for part in chunk.candidates[0].content.parts:
                if not part.text:
                    continue
                if hasattr(part, "thought") and part.thought:
                    thought_buffer += part.text
                else:
                    json_buffer += part.text

        result = {
            "thought_process": thought_buffer,
            "structured_output": None,
            "raw_json": json_buffer,
        }
        if json_buffer.strip():
            try:
                result["structured_output"] = json.loads(json_buffer.strip())
            except json.JSONDecodeError:
                pass

        return result


# Singleton instance
gemini_service = GeminiService()
