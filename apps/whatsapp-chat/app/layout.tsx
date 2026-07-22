import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LaundryKhalas WhatsApp Agent — Local Test Console",
  description: "Standalone WhatsApp-style test console for the LaundryKhalas WhatsApp Agent.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
