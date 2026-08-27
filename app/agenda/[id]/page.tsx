"use client"

import { use } from "react"
import { useState } from "react"
import Link from "next/link"
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Database,
  ExternalLink,
  FileSearch,
  Layers,
  MapPin,
  Send,
  Share2,
  Sparkles,
  Vote,
  Coins,
} from "lucide-react"
import { toast } from "sonner"

export default function AgendaTrackerComingSoonPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const resolvedParams = use(params)
  const agendaId = resolvedParams.id

  const [email, setEmail] = useState("")
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubscribe = (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !email.includes("@")) {
      toast.error("Please enter a valid email address.")
      return
    }

    setLoading(true)
    setTimeout(() => {
      setLoading(false)
      setSubmitted(true)
      toast.success(`You're subscribed for Agenda #${agendaId} updates!`, {
        description: "We will notify you when graph-backed evidence is published for this agenda.",
      })
    }, 600)
  }

  const handleShare = () => {
    if (typeof navigator !== "undefined" && navigator.share) {
      navigator
        .share({
          title: `NepalReforms Tracker — Agenda #${agendaId} Detail`,
          text: `Tracking ground truth and budget movement for Agenda #${agendaId} on NepalReforms Tracker.`,
          url: window.location.href,
        })
        .catch(() => {})
    } else if (typeof navigator !== "undefined") {
      navigator.clipboard.writeText(window.location.href)
      toast.success("Link copied to clipboard!")
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#080c14] text-slate-100 selection:bg-emerald-500/30 selection:text-emerald-300">
      {/* Top Status Bar */}
      <div className="border-b border-emerald-900/40 bg-emerald-950/80 text-emerald-200 text-xs py-2.5 px-4 backdrop-blur">
        <div className="container mx-auto flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400"></span>
            </span>
            <span className="font-mono uppercase tracking-wider font-semibold text-emerald-300">
              AGENDA #{agendaId} • GRAPH INGESTION IN PROGRESS
            </span>
            <span className="hidden sm:inline text-emerald-500/60">•</span>
            <span className="hidden sm:inline text-emerald-300/80">
              Verified Promise Linking & Red Book Extraction Underway
            </span>
          </div>
          <div className="flex items-center gap-3 text-emerald-300">
            <span className="font-mono text-[11px]">TARGET LAUNCH: Q2 2026</span>
            <button
              onClick={handleShare}
              className="flex items-center gap-1 hover:text-white transition-colors cursor-pointer text-xs"
              aria-label="Share agenda tracker link"
            >
              <Share2 className="h-3.5 w-3.5" />
              <span>Share</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Header */}
      <header className="border-b border-slate-800/80 bg-slate-950/70 backdrop-blur-md sticky top-0 z-40">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between gap-4">
            <Link href="/" className="flex items-center gap-3 hover:opacity-90 transition-opacity">
              <div className="h-9 w-9 rounded-lg bg-emerald-950 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-lg font-mono">
                NR
              </div>
              <div>
                <div className="text-base font-bold text-white flex items-center gap-2">
                  NepalReforms <span className="text-xs font-mono font-medium px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800">Tracker</span>
                </div>
                <div className="text-[11px] text-slate-400 hidden sm:block">
                  Public Accountability Intelligence Backbone
                </div>
              </div>
            </Link>

            <nav className="flex items-center gap-4 text-sm font-medium">
              <Link
                href="/"
                className="text-slate-400 hover:text-white transition-colors hidden sm:inline"
              >
                Tracker Overview
              </Link>
              <Link
                href={`https://nepalreforms.com/agenda/${encodeURIComponent(agendaId)}`}
                className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-600/40 bg-emerald-950/60 px-3.5 py-1.5 text-xs text-emerald-300 hover:bg-emerald-900/80 hover:text-white transition-colors"
              >
                <span>Read Agenda #{agendaId} Proposal</span>
                <ExternalLink className="h-3.5 w-3.5 text-emerald-400" />
              </Link>
            </nav>
          </div>
        </div>
      </header>

      <main className="flex-1 py-12 sm:py-20">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-4xl space-y-8">
          {/* Breadcrumb back */}
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-xs font-mono text-slate-400 hover:text-emerald-400 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Tracker Overview
          </Link>

          {/* Agenda Hero Card */}
          <div className="rounded-3xl border border-slate-800 bg-slate-950 p-8 sm:p-12 space-y-6 shadow-2xl relative overflow-hidden">
            <div className="absolute top-0 right-0 p-8 opacity-10 pointer-events-none">
              <div className="text-9xl font-mono font-extrabold text-emerald-400">#{agendaId}</div>
            </div>

            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-950/80 px-3.5 py-1.5 text-xs font-semibold text-emerald-300 font-mono">
              <Sparkles className="h-3.5 w-3.5 text-emerald-400" />
              <span>AGENDA #{agendaId} • COMING SOON</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-white text-balance">
              Deep Evidence & Accountability Graph for Agenda #{agendaId}
            </h1>

            <p className="text-base sm:text-lg text-slate-400 leading-relaxed max-w-2xl">
              We are currently compiling and verifying the <strong>political promises</strong>,{" "}
              <strong>Red Book budget allocations</strong>, and <strong>ground-reality verification audits</strong> for
              this specific reform agenda.
            </p>

            {/* Ingestion Pipeline Checklist for this agenda */}
            <div className="grid gap-3 sm:grid-cols-3 pt-2">
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-1">
                <div className="flex items-center justify-between text-xs font-mono text-emerald-400">
                  <span>STEP 1</span>
                  <span className="bg-emerald-950 px-2 py-0.5 rounded text-[10px] border border-emerald-800">DONE</span>
                </div>
                <div className="text-sm font-semibold text-white">Ontology & Schema</div>
                <p className="text-xs text-slate-400">Agenda mapped to 31 national reform schema nodes.</p>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-1">
                <div className="flex items-center justify-between text-xs font-mono text-blue-400">
                  <span>STEP 2</span>
                  <span className="bg-blue-950 px-2 py-0.5 rounded text-[10px] border border-blue-800">ACTIVE</span>
                </div>
                <div className="text-sm font-semibold text-white">Manifesto Linkage</div>
                <p className="text-xs text-slate-400">Connecting RSP, NC, CPN-UML manifesto commitments.</p>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-1">
                <div className="flex items-center justify-between text-xs font-mono text-slate-400">
                  <span>STEP 3</span>
                  <span className="bg-slate-800 px-2 py-0.5 rounded text-[10px] border border-slate-700">Q2 2026</span>
                </div>
                <div className="text-sm font-semibold text-white">Red Book Ledger</div>
                <p className="text-xs text-slate-400">Line-item budget releases & divergence detector.</p>
              </div>
            </div>

            {/* Notification form */}
            <div className="pt-4 border-t border-slate-800/80">
              <div className="max-w-xl space-y-3">
                <div className="text-sm font-semibold text-slate-200">
                  Get notified when the deep tracker graph for Agenda #{agendaId} is published:
                </div>
                {!submitted ? (
                  <form onSubmit={handleSubscribe} className="flex flex-col sm:flex-row gap-2">
                    <input
                      type="email"
                      placeholder="Enter your email..."
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="h-11 px-4 rounded-lg bg-slate-900/90 border border-slate-700 text-white placeholder:text-slate-500 text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 flex-1"
                      required
                      aria-label="Email for agenda notification"
                    />
                    <button
                      type="submit"
                      disabled={loading}
                      className="h-11 px-6 bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-semibold rounded-lg text-sm transition-all duration-200 cursor-pointer shrink-0 flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                      {loading ? (
                        <>
                          <span className="h-4 w-4 border-2 border-slate-950 border-t-transparent animate-spin rounded-full" />
                          <span>Subscribing...</span>
                        </>
                      ) : (
                        <>
                          <span>Notify Me</span>
                          <Send className="h-4 w-4" />
                        </>
                      )}
                    </button>
                  </form>
                ) : (
                  <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/40 p-4 text-emerald-300 flex items-center gap-3">
                    <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
                    <div className="text-sm font-medium">
                      You are on the alert list for Agenda #{agendaId}.
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Jump to Editorial Proposal */}
            <div className="pt-2 flex flex-wrap items-center gap-4">
              <Link
                href={`https://nepalreforms.com/agenda/${encodeURIComponent(agendaId)}`}
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold px-5 py-2.5 text-sm transition-colors cursor-pointer"
              >
                <span>Read Full Proposal on NepalReforms Platform</span>
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="https://nepalreforms.com/#agendas-section"
                className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors"
              >
                View all 31 Agendas
                <ChevronRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-slate-950 py-10">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-3">
          <div className="flex justify-center items-center gap-2 text-white font-semibold text-sm">
            <span>NepalReforms Tracker</span>
            <span>•</span>
            <span className="text-emerald-400">Agenda #{agendaId}</span>
          </div>
          <p className="text-xs text-slate-500">
            Public reform platform available at{" "}
            <Link href="https://nepalreforms.com" className="text-slate-400 hover:underline">
              nepalreforms.com
            </Link>{" "}
            • Powered by{" "}
            <Link href="https://nexalaris.com" target="_blank" className="text-emerald-400 hover:underline">
              Nexalaris Tech Pvt. Ltd.
            </Link>
          </p>
        </div>
      </footer>
    </div>
  )
}
