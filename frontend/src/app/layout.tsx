import type { Metadata } from "next";
import { JetBrains_Mono, Manrope } from "next/font/google";
import { Providers } from "@/components/providers";
import { SiteHeader } from "@/components/site-header";
import { cn } from "@/lib/utils";
import "./globals.css";

// Brand typography (brand.md): Manrope for UI and headings, JetBrains Mono for
// times, doses and other numbers that need to line up.
const sans = Manrope({ subsets: ["latin"], variable: "--font-sans" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: { default: "MedGuard", template: "%s · MedGuard" },
  description: "Your medicines, safely timed.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // suppressHydrationWarning: next-themes sets the theme class before React hydrates.
    <html lang="en" className={cn("font-sans antialiased", sans.variable, mono.variable)} suppressHydrationWarning>
      <body className="flex min-h-dvh flex-col">
        <Providers>
          <a
            href="#main"
            className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:ring-2 focus:ring-ring"
          >
            Skip to content
          </a>
          <SiteHeader />
          <main id="main" className="flex-1">
            {children}
          </main>
          <footer className="border-t border-border">
            <div className="mx-auto max-w-5xl px-4 py-6 text-sm text-muted-foreground md:px-6">
              MedGuard helps you organise medicine timing. It isn&apos;t medical advice. Check every routine with
              your doctor or pharmacist, and never stop or change a medicine without talking to them.
            </div>
          </footer>
        </Providers>
      </body>
    </html>
  );
}
