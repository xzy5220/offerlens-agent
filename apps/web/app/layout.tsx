import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OfferLens — Career Intelligence Agents",
  description: "Evidence-grounded job analysis and interview preparation powered by LangGraph.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
