import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Axon Dashboard",
  description: "Axon Agent Scale-Kit — Web Management Dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased">
        {children}
      </body>
    </html>
  );
}
