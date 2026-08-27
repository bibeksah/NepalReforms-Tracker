"use client"

import Link from "next/link"
import { ArrowLeft, ArrowRight, Sparkles, Activity } from "lucide-react"

export default function TrackerNotFound() {
  return (
    <div className="min-h-screen flex flex-col bg-[#080c14] text-slate-100 selection:bg-emerald-500/30 selection:text-emerald-300">
      <header className="border-b border-slate-800/80 bg-slate-950/70 backdrop-blur-md sticky top-0 z-40">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between gap-4">
            <Link href="/" className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-emerald-950 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-lg font-mono">
                NR
              </div>
              <div className="text-base font-bold text-white flex items-center gap-2">
                NepalReforms <span className="text-xs font-mono font-medium px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">Tracker</span>
              </div>
            </Link>
            <Link
              href="https://nepalreforms.com"
              className="text-xs text-slate-400 hover:text-white transition-colors"
            >
              Back to nepalreforms.com
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center py-16 px-4">
        <div className="max-w-xl text-center space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-950/60 px-3.5 py-1.5 text-xs font-semibold text-emerald-300 font-mono">
            <Sparkles className="h-3.5 w-3.5 text-emerald-400" />
            <span>NEPALREFORMS TRACKER • COMING SOON</span>
          </div>

          <h1 className="text-3xl sm:text-4xl font-extrabold text-white">
            This Tracker Page is Coming Soon
          </h1>

          <p className="text-slate-400 text-sm sm:text-base leading-relaxed">
            The full graph visualizer, budget event flows, and ground audit feeds are currently under active development.
          </p>

          <div className="flex flex-wrap justify-center gap-3 pt-2">
            <Link
              href="/"
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold px-5 py-2.5 text-sm transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Tracker Home</span>
            </Link>
            <Link
              href="https://nepalreforms.com"
              className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-5 py-2.5 text-sm text-slate-200 hover:bg-slate-800 transition-colors"
            >
              <span>Explore 31 Agendas</span>
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </main>

      <footer className="border-t border-slate-800 bg-slate-950 py-6 text-center text-xs text-slate-500">
        NepalReforms Tracker • Powered by Nexalaris Tech
      </footer>
    </div>
  )
}
