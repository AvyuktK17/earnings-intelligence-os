import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Nav from "@/components/Nav";
import { ColdStartNotice } from "@/components/States";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Earnings Intelligence OS",
  description: "Semiconductor Research Terminal",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full font-sans text-sm">
        <div className="flex min-h-screen flex-col lg:flex-row">
          <Nav />
          <div className="flex min-w-0 flex-1 flex-col">
            <ColdStartNotice />
            <main className="min-w-0 flex-1 px-4 py-5 sm:px-6 lg:px-8">
              <div className="page-shell">{children}</div>
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
