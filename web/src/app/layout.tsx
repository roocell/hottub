import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LAN Hot Tub Controller",
  description: "Local-only hot tub controller"
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
