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

// metadataBase makes the social-preview image URL absolute, so LinkedIn,
// X, and Slack render a rich link card. The opengraph-image.png next to
// this file is picked up by Next automatically for og:image/twitter:image.
export const metadata: Metadata = {
  metadataBase: new URL("https://earnings-intelligence-os.vercel.app"),
  title: "Earnings Intelligence OS",
  description:
    "Evidence-grounded semiconductor equity research: AI drafts claims from SEC filings, humans approve them, and every published sentence links to its exact source.",
  openGraph: {
    title: "Earnings Intelligence OS",
    description:
      "AI drafts, humans approve. A semiconductor research terminal where every claim is grounded in a literal SEC-filing quote.",
    url: "/",
    siteName: "Earnings Intelligence OS",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Earnings Intelligence OS",
    description:
      "AI drafts, humans approve. A semiconductor research terminal where every claim is grounded in a literal SEC-filing quote.",
  },
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
