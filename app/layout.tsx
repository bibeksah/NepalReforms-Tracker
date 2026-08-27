import type { Metadata } from "next"
import { Toaster } from "sonner"
import "./globals.css"

export const metadata: Metadata = {
  title: "NepalReforms Tracker — The Public Accountability Engine",
  description:
    "Connecting political manifesto promises, Red Book budget movements, and ground-reality verification into a verifiable knowledge graph for Nepal.",
  keywords: [
    "NepalReforms Tracker",
    "Nepal budget tracker",
    "Red Book intelligence",
    "Nepal governance tracker",
    "Manifesto promise tracking Nepal",
  ],
  openGraph: {
    title: "NepalReforms Tracker — Public Accountability Engine",
    description:
      "Connecting political manifesto promises, Red Book budget movements, and ground-reality verification into a verifiable knowledge graph for Nepal.",
    url: "https://tracker.nepalreforms.com",
    type: "website",
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className="dark">
      <body className="font-sans antialiased min-h-screen flex flex-col bg-background text-foreground selection:bg-emerald-500/30 selection:text-emerald-300">
        {children}
        <Toaster position="bottom-right" richColors theme="dark" />
      </body>
    </html>
  )
}
