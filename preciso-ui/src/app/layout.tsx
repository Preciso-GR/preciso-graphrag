import type { Metadata } from "next";
import { Anton, Barlow_Condensed, Geist, Geist_Mono } from "next/font/google";
import { ThemeProvider } from "@/context/ThemeContext";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
const anton = Anton({ variable: "--font-anton", subsets: ["latin"], weight: "400" });
const barlowCondensed = Barlow_Condensed({
  variable: "--font-barlow-condensed",
  subsets: ["latin"],
  weight: ["700", "800", "900"],
});

export const metadata: Metadata = {
  title: "Preciso — Precise knowledge graphs from your documents",
  description:
    "Drop files. Your agent builds a queryable knowledge graph — locally. No cloud, no pipeline, no config. 95/100 benchmark score, zero hallucinations.",
  keywords: ["GraphRAG", "knowledge graph", "MCP", "RAG", "AI", "local-first"],
  openGraph: {
    title: "Preciso — Precise knowledge graphs from your documents",
    description: "Drop files. Agent extracts entities and relationships. Local graph. Zero cloud.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${anton.variable} ${barlowCondensed.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
