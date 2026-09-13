import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "ResolveAI — AI Support Operations", template: "%s · ResolveAI" },
  description: "Evidence-gated, auditable, human-in-the-loop AI support operations for customer support teams.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
