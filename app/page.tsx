"use client"

import { useState } from "react"
import Link from "next/link"
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Database,
  ExternalLink,
  FileSearch,
  GitBranch,
  Layers,
  MapPin,
  Network,
  ShieldCheck,
  Sparkles,
  Vote,
  Coins,
  AlertTriangle,
  Send,
  Share2,
  Check,
} from "lucide-react"
import { toast } from "sonner"

export default function TrackerHomePage() {
  const [email, setEmail] = useState("")
  const [activeTab, setActiveTab] = useState<"promise" | "budget" | "divergence" | "parliament">("promise")
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
      toast.success("You're on the Tracker early access list!", {
        description: "We'll notify you as soon as the live graph visualizer goes live.",
      })
    }, 600)
  }

  const handleShare = () => {
    if (typeof navigator !== "undefined" && navigator.share) {
      navigator
        .share({
          title: "NepalReforms Tracker — Coming Soon",
          text: "Tracking Nepal's political promises, Red Book budgets, and ground reality with a verified knowledge graph.",
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
              ALPHA ENGINE INGESTION ACTIVE
            </span>
            <span className="hidden sm:inline text-emerald-500/60">•</span>
            <span className="hidden sm:inline text-emerald-300/80">
              Neo4j Graph Database + Red Book Budget Parser in Testing
            </span>
          </div>
          <div className="flex items-center gap-3 text-emerald-300">
            <span className="font-mono text-[11px]">TARGET LAUNCH: Q2 2026</span>
            <button
              onClick={handleShare}
              className="flex items-center gap-1 hover:text-white transition-colors cursor-pointer text-xs"
              aria-label="Share tracker link"
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
                href="https://nepalreforms.com"
                className="text-slate-400 hover:text-white transition-colors hidden md:inline"
              >
                Civic Platform
              </Link>
              <Link
                href="https://nepalreforms.com/#agendas-section"
                className="text-slate-400 hover:text-white transition-colors hidden sm:inline"
              >
                27 Agendas
              </Link>
              <Link
                href="https://nepalreforms.com/testimonials"
                className="text-slate-400 hover:text-white transition-colors hidden sm:inline"
              >
                Citizen Voices
              </Link>
              <Link
                href="https://nepalreforms.com"
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900 px-3.5 py-1.5 text-xs text-slate-200 hover:bg-slate-800 hover:text-white transition-colors"
              >
                <span>Visit nepalreforms.com</span>
                <ExternalLink className="h-3.5 w-3.5 text-slate-400" />
              </Link>
            </nav>
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero Section */}
        <section className="relative overflow-hidden py-16 sm:py-24 border-b border-slate-800/80 bg-gradient-to-b from-slate-950 via-[#080c14] to-[#0a101d]">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8">
            <div className="max-w-4xl mx-auto text-center space-y-6">
              <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-950/60 px-3.5 py-1.5 text-xs font-semibold text-emerald-300 font-mono shadow-xs">
                <Sparkles className="h-3.5 w-3.5 text-emerald-400" />
                <span>NEPALREFORMS INTELLIGENCE BACKBONE • TRACKER V1.0</span>
              </div>

              <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl lg:text-6xl text-balance">
                The Public Accountability Engine for Nepal’s Governance.
              </h1>

              <p className="text-base sm:text-xl text-slate-400 leading-relaxed max-w-2xl mx-auto text-balance">
                Connecting <strong>manifesto promises</strong>, <strong>Red Book budget lines</strong>,{" "}
                <strong>money flow events</strong>, and <strong>ground-reality evidence</strong> into an open,
                verifiable public knowledge graph.
              </p>

              {/* Early Access Notification Form */}
              <div className="pt-4 max-w-xl mx-auto">
                {!submitted ? (
                  <form onSubmit={handleSubscribe} className="space-y-3">
                    <div className="flex flex-col sm:flex-row gap-2">
                      <input
                        type="email"
                        placeholder="Enter your email for early beta access..."
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="h-11 px-4 rounded-lg bg-slate-900/90 border border-slate-700 text-white placeholder:text-slate-500 text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 flex-1"
                        required
                        aria-label="Email address for tracker early access"
                      />
                      <button
                        type="submit"
                        disabled={loading}
                        className="h-11 px-6 bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-semibold rounded-lg text-sm transition-all duration-200 cursor-pointer shrink-0 flex items-center justify-center gap-2 disabled:opacity-50"
                      >
                        {loading ? (
                          <>
                            <span className="h-4 w-4 border-2 border-slate-950 border-t-transparent animate-spin rounded-full" />
                            <span>Adding...</span>
                          </>
                        ) : (
                          <>
                            <span>Get Notified</span>
                            <Send className="h-4 w-4" />
                          </>
                        )}
                      </button>
                    </div>
                    <div className="flex items-center justify-center gap-4 text-xs text-slate-500">
                      <span>✓ Zero spam</span>
                      <span>•</span>
                      <span>✓ Exact provenance</span>
                      <span>•</span>
                      <span>✓ Open civic data</span>
                    </div>
                  </form>
                ) : (
                  <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/40 p-4 text-emerald-300 flex items-center justify-center gap-3">
                    <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
                    <div className="text-sm font-medium text-left">
                      You are in line for early beta access! We will send you an invite when the live visualizer opens.
                    </div>
                  </div>
                )}
              </div>

              {/* Quick Links */}
              <div className="pt-2 flex flex-wrap items-center justify-center gap-3">
                <Link
                  href="https://nepalreforms.com/#agendas-section"
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/80 px-4 py-2.5 text-sm font-medium text-slate-200 hover:bg-slate-800 transition-colors"
                >
                  Explore 27 Reform Agendas
                  <ArrowRight className="h-4 w-4 text-emerald-400" />
                </Link>
                <Link
                  href="https://nepalreforms.com/testimonials"
                  className="inline-flex items-center gap-2 rounded-lg border border-transparent px-4 py-2.5 text-sm font-medium text-slate-400 hover:text-white transition-colors"
                >
                  Read Community Voices
                  <ChevronRight className="h-4 w-4" />
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* Ingestion & Telemetry Grid */}
        <section className="py-12 bg-slate-950 border-b border-slate-800/80">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
              <div>
                <p className="text-xs font-mono font-semibold uppercase tracking-wider text-emerald-400">
                  DATABASE READINESS & INGESTION TELEMETRY
                </p>
                <h2 className="text-2xl font-bold tracking-tight text-white mt-1">
                  What’s Being Ingested & Verified
                </h2>
              </div>
              <span className="border border-slate-800 bg-slate-900 text-slate-300 font-mono text-xs px-3 py-1 rounded-full">
                STAGE: GRAPH ENGINE INGESTION
              </span>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 hover:border-slate-700 transition-colors">
                <div className="flex items-center justify-between text-slate-400">
                  <span className="text-xs font-mono">CORE_AGENDAS</span>
                  <Layers className="h-4 w-4 text-emerald-400" />
                </div>
                <div className="mt-3 text-3xl font-extrabold font-mono text-white">27</div>
                <p className="mt-1 text-xs text-slate-400">Evidence-based reform proposals with baseline outcomes</p>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 hover:border-slate-700 transition-colors">
                <div className="flex items-center justify-between text-slate-400">
                  <span className="text-xs font-mono">PROMISES_PARSED</span>
                  <FileSearch className="h-4 w-4 text-blue-400" />
                </div>
                <div className="mt-3 text-3xl font-extrabold font-mono text-white">1,248+</div>
                <p className="mt-1 text-xs text-slate-400">RSP Bacha Patra & Parliamentary election pledges extracted</p>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 hover:border-slate-700 transition-colors">
                <div className="flex items-center justify-between text-slate-400">
                  <span className="text-xs font-mono">BUDGET_INDEXED</span>
                  <Coins className="h-4 w-4 text-amber-400" />
                </div>
                <div className="mt-3 text-3xl font-extrabold font-mono text-white">NPR 1.86T</div>
                <p className="mt-1 text-xs text-slate-400">Red Book federal & provincial budget line items mapped</p>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 hover:border-slate-700 transition-colors">
                <div className="flex items-center justify-between text-slate-400">
                  <span className="text-xs font-mono">MPS_TRACKED</span>
                  <Vote className="h-4 w-4 text-purple-400" />
                </div>
                <div className="mt-3 text-3xl font-extrabold font-mono text-white">275</div>
                <p className="mt-1 text-xs text-slate-400">House of Representatives members with local commitments</p>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 hover:border-slate-700 transition-colors">
                <div className="flex items-center justify-between text-slate-400">
                  <span className="text-xs font-mono">LOCAL_UNITS</span>
                  <MapPin className="h-4 w-4 text-rose-400" />
                </div>
                <div className="mt-3 text-3xl font-extrabold font-mono text-white">753</div>
                <p className="mt-1 text-xs text-slate-400">Municipalities & local bodies mapped for ground reality audits</p>
              </div>
            </div>
          </div>
        </section>

        {/* 4 Interactive Feature Pillars */}
        <section className="py-16 sm:py-20 bg-[#080c14] border-b border-slate-800/80">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
            <div className="max-w-3xl space-y-2">
              <span className="inline-block px-3 py-1 rounded-full text-xs font-mono font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800">
                SYSTEM PILLARS
              </span>
              <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
                Four Layers of Accountability Intelligence
              </h2>
              <p className="text-slate-400 text-sm sm:text-base">
                Explore how the Tracker moves beyond static promises to model real money flow and citizen ground truth.
              </p>
            </div>

            {/* Tab Buttons */}
            <div className="flex flex-wrap gap-2 p-1.5 rounded-xl bg-slate-900/90 border border-slate-800 max-w-2xl">
              <button
                onClick={() => setActiveTab("promise")}
                className={`px-4 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-all cursor-pointer ${
                  activeTab === "promise"
                    ? "bg-slate-800 text-white shadow-xs"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                1. Promise Engine
              </button>
              <button
                onClick={() => setActiveTab("budget")}
                className={`px-4 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-all cursor-pointer ${
                  activeTab === "budget"
                    ? "bg-slate-800 text-white shadow-xs"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                2. Red Book Flow
              </button>
              <button
                onClick={() => setActiveTab("divergence")}
                className={`px-4 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-all cursor-pointer ${
                  activeTab === "divergence"
                    ? "bg-slate-800 text-white shadow-xs"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                3. Reality Divergence
              </button>
              <button
                onClick={() => setActiveTab("parliament")}
                className={`px-4 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-all cursor-pointer ${
                  activeTab === "parliament"
                    ? "bg-slate-800 text-white shadow-xs"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                4. MP & District Map
              </button>
            </div>

            {/* Tab Content 1: Promise Engine */}
            {activeTab === "promise" && (
              <div className="rounded-2xl border border-slate-800 bg-slate-950 p-6 sm:p-8 space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-4">
                  <div>
                    <h3 className="text-xl font-bold text-white">Structured Manifesto Extraction</h3>
                    <p className="text-slate-400 text-xs sm:text-sm mt-1">
                      Promises are parsed into typed entities with exact page, paragraph, and party provenance.
                    </p>
                  </div>
                  <span className="self-start sm:self-center font-mono text-xs px-2.5 py-1 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                    STRICT_PROVENANCE_MODEL
                  </span>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono text-slate-500">SAMPLE PROMISE #RSP-BP-014</span>
                      <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-semibold text-[10px]">
                        VERIFIED_LINKAGE
                      </span>
                    </div>
                    <h4 className="font-semibold text-white text-sm">
                      Digitize all national identity & vital registration services within 100 days
                    </h4>
                    <p className="text-xs text-slate-400">
                      <strong>Source:</strong> RSP Bacha Patra 2079/2082 • Page 14 • Paragraph 3
                    </p>
                    <div className="text-xs text-slate-300 bg-slate-950 p-3 rounded-lg border border-slate-800 font-mono">
                      Linked Agenda: #1 (Digital Governance & Anti-Corruption Portal)
                      <br />
                      Implementing Body: MoCIT / Department of National ID
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono text-slate-500">SAMPLE PROMISE #NC-MAN-038</span>
                      <span className="px-2 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-800 font-semibold text-[10px]">
                        PENDING_BUDGET
                      </span>
                    </div>
                    <h4 className="font-semibold text-white text-sm">
                      Establish fast-track anti-graft special tribunals across all 7 provinces
                    </h4>
                    <p className="text-xs text-slate-400">
                      <strong>Source:</strong> NC Parliamentary Manifesto • Section 4.2
                    </p>
                    <div className="text-xs text-slate-300 bg-slate-950 p-3 rounded-lg border border-slate-800 font-mono">
                      Linked Agenda: #11 (Judicial & CIAA Autonomy Reform)
                      <br />
                      Implementing Body: Judicial Council / Ministry of Law
                    </div>
                  </div>
                </div>

                <div className="rounded-lg bg-slate-900 p-3 text-xs text-slate-400 flex items-start gap-2 border border-slate-800">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                  <span>
                    <strong>Zero Hallucination Rule:</strong> Links are never guessed. If a manifesto promise does not
                    resolve to an exact project ID, it stays unresolved for human operator review.
                  </span>
                </div>
              </div>
            )}

            {/* Tab Content 2: Red Book Flow */}
            {activeTab === "budget" && (
              <div className="rounded-2xl border border-slate-800 bg-slate-950 p-6 sm:p-8 space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-4">
                  <div>
                    <h3 className="text-xl font-bold text-white">Red Book Budget & Expenditure Tracking</h3>
                    <p className="text-slate-400 text-xs sm:text-sm mt-1">
                      Tracing funds from Ministry allocation to provincial treasury release to local execution.
                    </p>
                  </div>
                  <span className="self-start sm:self-center font-mono text-xs px-2.5 py-1 rounded bg-amber-950 text-amber-400 border border-amber-800">
                    EVENT_SOURCED_BUDGETS
                  </span>
                </div>

                <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <span className="font-bold text-white text-base">
                      Education Infrastructure Modernization (FY 2081/82)
                    </span>
                    <span className="font-mono text-sm font-bold text-emerald-400">Total: NPR 14.80 Arba</span>
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between text-xs font-mono text-slate-400">
                      <span>Allocated: NPR 14.8B</span>
                      <span>Released: NPR 10.2B (68.9%)</span>
                      <span className="text-emerald-400">Utilized: NPR 5.4B (36.4%)</span>
                    </div>
                    <div className="h-3 w-full bg-slate-800 rounded-full overflow-hidden flex">
                      <div className="bg-emerald-500 h-full" style={{ width: "36.4%" }} title="Utilized (36.4%)" />
                      <div className="bg-amber-500 h-full" style={{ width: "32.5%" }} title="Released unspent (32.5%)" />
                      <div className="bg-slate-700 h-full" style={{ width: "31.1%" }} title="Unreleased (31.1%)" />
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2 text-xs text-slate-400 font-mono pt-2">
                    <span className="bg-slate-950 px-2.5 py-1 rounded border border-slate-800">Code: 350-02-10</span>
                    <span className="bg-slate-950 px-2.5 py-1 rounded border border-slate-800">Agency: MoEST</span>
                    <span className="bg-slate-950 px-2.5 py-1 rounded border border-slate-800">Treasury: FCGO-2081</span>
                  </div>
                </div>
              </div>
            )}

            {/* Tab Content 3: Reality Divergence */}
            {activeTab === "divergence" && (
              <div className="rounded-2xl border border-slate-800 bg-slate-950 p-6 sm:p-8 space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-4">
                  <div>
                    <h3 className="text-xl font-bold text-white">Paper Truth vs. Ground Reality</h3>
                    <p className="text-slate-400 text-xs sm:text-sm mt-1">
                      Identifying where official ministry progress claims contradict citizen field audits.
                    </p>
                  </div>
                  <span className="self-start sm:self-center font-mono text-xs px-2.5 py-1 rounded bg-rose-950 text-rose-400 border border-rose-800">
                    DIVERGENCE_DETECTOR
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs sm:text-sm border-collapse">
                    <thead>
                      <tr className="border-b border-slate-800 bg-slate-900/80 text-slate-400">
                        <th className="p-3 font-semibold">Tracked Project</th>
                        <th className="p-3 font-semibold">Paper Truth (Official Claim)</th>
                        <th className="p-3 font-semibold">Ground Truth (Citizen Audit)</th>
                        <th className="p-3 font-semibold">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/80">
                      <tr className="hover:bg-slate-900/40">
                        <td className="p-3 font-medium text-white">Kathmandu-Terai Fast Track Tunnel Package</td>
                        <td className="p-3 text-emerald-400 font-mono">88% Complete (Ministry Report)</td>
                        <td className="p-3 text-amber-400 font-mono">64% Physical Progress (Geo-Audit Q1)</td>
                        <td className="p-3">
                          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-950 text-amber-300 border border-amber-800">
                            24% Divergence
                          </span>
                        </td>
                      </tr>
                      <tr className="hover:bg-slate-900/40">
                        <td className="p-3 font-medium text-white">District Hospital 50-Bed ICU (Rautahat)</td>
                        <td className="p-3 text-emerald-400 font-mono">100% Commissioned</td>
                        <td className="p-3 text-rose-400 font-mono">Equipment in boxes, 0 medical staff</td>
                        <td className="p-3">
                          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-950 text-rose-300 border border-rose-800">
                            Operational Deficit
                          </span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Tab Content 4: MP Heatmap */}
            {activeTab === "parliament" && (
              <div className="rounded-2xl border border-slate-800 bg-slate-950 p-6 sm:p-8 space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-4">
                  <div>
                    <h3 className="text-xl font-bold text-white">Constituency & MP Promise Heatmap</h3>
                    <p className="text-slate-400 text-xs sm:text-sm mt-1">
                      Tracking all 275 members of the House of Representatives by their local electoral pledges.
                    </p>
                  </div>
                  <span className="self-start sm:self-center font-mono text-xs px-2.5 py-1 rounded bg-purple-950 text-purple-400 border border-purple-800">
                    275_CONSTITUENCIES
                  </span>
                </div>

                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-white">Kathmandu - 4</span>
                      <span className="font-mono text-slate-500">Bagmati</span>
                    </div>
                    <p className="text-xs text-slate-400">Tracked Commitments: 18</p>
                    <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
                      <span className="text-emerald-400 font-bold">5 Done</span> •
                      <span className="text-blue-400 font-bold">7 Active</span> •
                      <span className="text-rose-400 font-bold">6 Stalled</span>
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-white">Dhanusha - 3</span>
                      <span className="font-mono text-slate-500">Madhesh</span>
                    </div>
                    <p className="text-xs text-slate-400">Tracked Commitments: 12</p>
                    <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
                      <span className="text-emerald-400 font-bold">2 Done</span> •
                      <span className="text-blue-400 font-bold">4 Active</span> •
                      <span className="text-rose-400 font-bold">6 Stalled</span>
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-white">Chitwan - 2</span>
                      <span className="font-mono text-slate-500">Bagmati</span>
                    </div>
                    <p className="text-xs text-slate-400">Tracked Commitments: 22</p>
                    <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
                      <span className="text-emerald-400 font-bold">8 Done</span> •
                      <span className="text-blue-400 font-bold">11 Active</span> •
                      <span className="text-rose-400 font-bold">3 Stalled</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Delivery Schedule Roadmap */}
        <section className="py-16 sm:py-20 bg-slate-950 border-b border-slate-800/80">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
            <div className="text-center max-w-2xl mx-auto space-y-3">
              <span className="inline-block px-3 py-1 rounded-full text-xs font-mono font-semibold bg-slate-900 text-slate-300 border border-slate-800">
                DELIVERY SCHEDULE
              </span>
              <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
                Roadmap to Launch
              </h2>
              <p className="text-slate-400 text-sm sm:text-base">
                Building systematically to guarantee that every data node is verifiable and free of phantom entries.
              </p>
            </div>

            <div className="grid gap-6 md:grid-cols-4 max-w-5xl mx-auto">
              <div className="rounded-2xl border border-emerald-500/40 bg-emerald-950/30 p-6 space-y-3 relative">
                <div className="h-1.5 w-full bg-emerald-500 rounded-full" />
                <div className="flex items-center justify-between text-xs font-mono font-semibold text-emerald-400">
                  <span>PHASE 1</span>
                  <span className="bg-emerald-900/80 px-2 py-0.5 rounded text-[10px] text-emerald-300 border border-emerald-700">
                    DONE
                  </span>
                </div>
                <h3 className="font-bold text-white">Foundation & Schema</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Neo4j ontology, typed budget contracts, agenda-promise linking pipelines, and consistency validation.
                </p>
              </div>

              <div className="rounded-2xl border border-blue-500/40 bg-blue-950/30 p-6 space-y-3 relative">
                <div className="h-1.5 w-full bg-blue-500 rounded-full" />
                <div className="flex items-center justify-between text-xs font-mono font-semibold text-blue-400">
                  <span>PHASE 2</span>
                  <span className="bg-blue-900/80 px-2 py-0.5 rounded text-[10px] text-blue-300 border border-blue-700">
                    CURRENT
                  </span>
                </div>
                <h3 className="font-bold text-white">Red Book & Ingestion</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Extracting Federal Red Book budget lines, multi-party manifestos, and ministry project identifiers.
                </p>
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-3 relative">
                <div className="h-1.5 w-full bg-slate-700 rounded-full" />
                <div className="flex items-center justify-between text-xs font-mono font-semibold text-slate-400">
                  <span>PHASE 3</span>
                  <span className="bg-slate-800 px-2 py-0.5 rounded text-[10px] text-slate-300 border border-slate-700">
                    Q2 2026
                  </span>
                </div>
                <h3 className="font-bold text-white">Public Beta Explorer</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Interactive web graph, constituency filters, money flow visualizer, and exportable audit datasets.
                </p>
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 space-y-3 relative">
                <div className="h-1.5 w-full bg-slate-700 rounded-full" />
                <div className="flex items-center justify-between text-xs font-mono font-semibold text-slate-400">
                  <span>PHASE 4</span>
                  <span className="bg-slate-800 px-2 py-0.5 rounded text-[10px] text-slate-300 border border-slate-700">
                    Q3 2026
                  </span>
                </div>
                <h3 className="font-bold text-white">Citizen Oracle Network</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Decentralized field audits, photo verification, community oversight bounty program, and open APIs.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Citizen & Researcher Participation Callout */}
        <section className="py-16 sm:py-20 bg-gradient-to-b from-slate-950 to-[#060a11]">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-4xl">
            <div className="rounded-3xl border border-emerald-900/60 bg-emerald-950/40 p-8 sm:p-12 text-center space-y-6 backdrop-blur">
              <span className="inline-block px-3 py-1 rounded-full text-xs font-mono font-semibold bg-emerald-900 text-emerald-300 border border-emerald-700">
                JOIN THE ACCURACY INITIATIVE
              </span>
              <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
                Help Us Verify Ground Reality Across Nepal
              </h2>
              <p className="text-emerald-200/90 text-sm sm:text-base max-w-2xl mx-auto leading-relaxed">
                Whether you are an investigative journalist, data analyst, legal researcher, or active citizen in your
                district — you can join as a verified ground auditor.
              </p>

              <div className="grid gap-3 sm:grid-cols-3 pt-2 text-left">
                <div className="rounded-xl border border-emerald-900/60 bg-slate-950/80 p-4">
                  <div className="text-sm font-semibold text-white">1. Field Audits</div>
                  <p className="mt-1 text-xs text-slate-400">
                    Verify local school, hospital, and infrastructure progress in your municipality.
                  </p>
                </div>
                <div className="rounded-xl border border-emerald-900/60 bg-slate-950/80 p-4">
                  <div className="text-sm font-semibold text-white">2. Budget Auditing</div>
                  <p className="mt-1 text-xs text-slate-400">
                    Analyze district expenditure notices and municipal procurement tenders.
                  </p>
                </div>
                <div className="rounded-xl border border-emerald-900/60 bg-slate-950/80 p-4">
                  <div className="text-sm font-semibold text-white">3. Open Data APIs</div>
                  <p className="mt-1 text-xs text-slate-400">
                    Query graph nodes programmatically for journalism and civic tech apps.
                  </p>
                </div>
              </div>

              <div className="pt-4 flex flex-wrap justify-center gap-4">
                <Link
                  href="https://nepalreforms.com"
                  className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold px-6 py-3 text-sm transition-colors cursor-pointer"
                >
                  <span>Explore Main Platform</span>
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  href="https://nepalreforms.com/create-opinion"
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/90 hover:bg-slate-800 text-slate-200 font-medium px-6 py-3 text-sm transition-colors cursor-pointer"
                >
                  <span>Submit Citizen Feedback</span>
                  <ChevronRight className="h-4 w-4" />
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-slate-950 py-12">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center space-y-4">
            <div className="flex justify-center items-center gap-3">
              <div className="h-7 w-7 rounded bg-emerald-950 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-sm font-mono">
                NR
              </div>
              <span className="text-base font-semibold text-white">NepalReforms • Tracker</span>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 max-w-lg mx-auto">
              The public accountability intelligence engine for Nepal, providing graph-backed evidence for reform progress.
            </p>
            <p className="text-xs text-slate-500">
              Powered by{" "}
              <Link
                href="https://nexalaris.com/"
                target="_blank"
                className="font-medium text-emerald-400 hover:underline"
              >
                Nexalaris Tech Pvt. Ltd.
              </Link>
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
