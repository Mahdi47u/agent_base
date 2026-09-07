import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent Base",
  description: "Reusable tool-using assistant starter",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
