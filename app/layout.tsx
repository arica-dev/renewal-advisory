import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Renewal Advisor",
  description: "Small-group renewal analysis for benefits brokers: what's driving the increase, whether to push back, and which option fits the budget.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          precedence="default"
          href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap"
        />
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="min-w-0 flex-1 px-5 py-6 md:px-12 md:py-8">
            <div className="mx-auto flex max-w-[1160px] flex-col gap-6">
              {children}
              <footer className="border-t border-line pt-4 text-xs leading-relaxed text-ink-3">
                Concept by Arica. Not affiliated with or endorsed by Clasp. Sample groups, people and renewal
                rates are synthetic. 2027 filings from ratereview.healthcare.gov (requested, not final), retrieved
                Sep 24, 2026. Aging uses the ACA federal default age curve.
              </footer>
            </div>
          </main>
        </div>
      </body>
    </html>
  );
}
