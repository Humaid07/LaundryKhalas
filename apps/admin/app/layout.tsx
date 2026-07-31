import type { Metadata } from "next";
import { Bricolage_Grotesque, Geist, Geist_Mono } from "next/font/google";
import { QueryProvider } from "@/lib/query-client";
import { ThemeProvider } from "@/lib/dashboard/theme-provider";
import { AuthProvider } from "@/lib/dashboard/auth-context";
import "./globals.css";

// Deliberate type trio — display (Bricolage Grotesque) / body (Geist Sans) /
// numeric (Geist Mono). Geist gives a clean, engineered UI voice; Bricolage
// keeps an editorial display face for page titles + hero KPI numbers.
const display = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});
const body = Geist({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});
const numeric = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-numeric",
  display: "swap",
});

export const metadata: Metadata = {
  title: "LaundryKhalas — Operations Command Center",
  description:
    "Internal command center for LaundryKhalas laundry & cleaning operations across the GCC.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${display.variable} ${body.variable} ${numeric.variable}`}
    >
      <body className="bg-canvas font-sans text-ink antialiased">
        <ThemeProvider>
          <QueryProvider>
            <AuthProvider>{children}</AuthProvider>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
