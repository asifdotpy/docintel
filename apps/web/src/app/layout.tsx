import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "DocIntel — Document Intelligence",
  description: "Upload, extract, validate, correct, and search business documents.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <nav className="border-b px-8 py-3 flex items-center gap-5 text-sm">
          <Link href="/" className="font-semibold">
            DocIntel
          </Link>
          <Link href="/upload" className="text-gray-700 hover:text-blue-600">
            Upload
          </Link>
          <Link href="/search" className="text-gray-700 hover:text-blue-600">
            Search
          </Link>
        </nav>
        <div className="flex-1">{children}</div>
      </body>
    </html>
  );
}
