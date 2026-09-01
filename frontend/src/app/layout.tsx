import type { Metadata } from "next";
import { ThemeProvider } from "next-themes";
import { QueryProvider } from "@/components/QueryProvider";
import { Header } from "@/components/layout/Header";
import "./globals.css";

export const metadata: Metadata = {
  title: "AIOps Sentinel",
  description: "Self-aware observability platform with MAD/CUSUM anomaly detection and Gemini reasoning",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-[#0a0a0f] text-slate-200 antialiased">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
          <QueryProvider>
            <div className="flex flex-col min-h-screen">
              <Header />
              <main className="flex-1 container mx-auto px-4 py-6 max-w-screen-2xl">
                {children}
              </main>
            </div>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
