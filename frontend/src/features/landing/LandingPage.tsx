import {
  Activity,
  ArrowRight,
  Boxes,
  Building2,
  Calendar,
  CheckCircle2,
  ChevronRight,
  Cpu,
  FileCheck2,
  GitBranch,
  GitFork,
  Layers,
  Menu,
  Network,
  Radio,
  ShieldAlert,
  ShieldCheck,
  Users,
  Wrench,
  X,
} from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { BrandMark } from '@/ui/Brand'
import { CampusMap } from '@/ui/CampusMap'
import { cn } from '@/ui/cn'

const INNOVATION_CARDS = [
  {
    number: '01',
    title: 'Collision Engine',
    subtitle: 'Operational Conflict Detection',
    description:
      'Detects operational conflicts before actions are executed, validating room availability, technician assignments, resources and operational constraints.',
    icon: ShieldAlert,
    accent: 'border-brand-blue/30 bg-brand-pale/40 text-brand-blue',
  },
  {
    number: '02',
    title: 'Cascading Event Intelligence',
    subtitle: 'Infrastructure Impact Graph',
    description:
      'Understands how an incident propagates through connected infrastructure, buildings, rooms and academic activities.',
    icon: GitBranch,
    accent: 'border-brand-deep/30 bg-brand-light/50 text-brand-deep',
  },
  {
    number: '03',
    title: 'Synthetic Reality Engine',
    subtitle: 'Isolated Strategy Simulation',
    description:
      'Simulates alternative recovery strategies in an isolated environment before committing changes to live campus operations.',
    icon: Boxes,
    accent: 'border-brand-blue/30 bg-brand-pale/40 text-brand-blue',
  },
  {
    number: '04',
    title: 'Invoice-to-Inventory Intelligence',
    subtitle: 'Autonomous Procurement Audit',
    description:
      'Validates supplier invoices against approved purchase orders and goods receipts before inventory is updated.',
    icon: FileCheck2,
    accent: 'border-brand-deep/30 bg-brand-light/50 text-brand-deep',
  },
]

const WORKFLOW_STEPS = [
  {
    step: '01',
    tag: 'UNDERSTAND',
    title: 'Intelligent Intake & Detection',
    description: 'Identify incidents, operational problems and affected resources across campus nodes in real time.',
    icon: Radio,
  },
  {
    step: '02',
    tag: 'TRACE',
    title: 'Multi-layer Dependency Graph',
    description: 'Discover direct and cascading consequences through campus dependencies, utility lines and schedules.',
    icon: GitFork,
  },
  {
    step: '03',
    tag: 'SIMULATE',
    title: 'Synthetic Conflict Testing',
    description: 'Evaluate possible recovery strategies without modifying live operations or disrupting lectures.',
    icon: Layers,
  },
  {
    step: '04',
    tag: 'EXECUTE',
    title: 'Validated Operations Dispatch',
    description: 'Validate and execute approved operational actions with closed-loop audit logging and live tracking.',
    icon: CheckCircle2,
  },
]

const CONNECTED_DOMAINS = [
  { label: 'Academic Schedules', icon: Calendar, desc: 'Exam clashes, room allocations & timetable sync' },
  { label: 'Buildings & Rooms', icon: Building2, desc: 'Spatial boundaries, zone hitboxes & floorplans' },
  { label: 'Facilities', icon: Cpu, desc: 'HVAC, electrical grids, backup generators & water lines' },
  { label: 'Maintenance Teams', icon: Users, desc: 'Skill routing, work capacity & shift rosters' },
  { label: 'Technicians', icon: Wrench, desc: 'Dispatch queues, real-time status & job sign-offs' },
  { label: 'Infrastructure', icon: Network, desc: 'Core network links, power distribution & sensors' },
  { label: 'Inventory', icon: Boxes, desc: 'Real-time spares, ledger tracking & replenishment' },
  { label: 'Procurement', icon: FileCheck2, desc: 'Three-way invoice verification & purchase orders' },
]

export function LandingPage() {
  const navigate = useNavigate()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [selectedMapRegion, setSelectedMapRegion] = useState<string | null>('EEC-MAIN')

  const scrollToSection = (id: string) => {
    setMobileMenuOpen(false)
    const element = document.getElementById(id)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' })
    }
  }

  return (
    <div className="min-h-screen bg-brand-bg text-brand-text font-sans selection:bg-brand-light selection:text-brand-deep overflow-x-hidden">
      {/* ── FLOATING NAVIGATION BAR ── */}
      <nav
        aria-label="Main Navigation"
        className="fixed top-4 inset-x-0 z-50 flex justify-center px-4"
      >
        <div className="glass-capsule w-full max-w-5xl rounded-full px-5 py-2.5 flex items-center justify-between transition-all">
          <div className="button-shine" />

          {/* Logo & Brand */}
          <Link
            to="/"
            className="relative z-10 flex items-center gap-2.5 focus-visible:outline-2 focus-visible:outline-accent rounded-full p-1"
          >
            <BrandMark className="size-7" />
            <span className="text-lg font-bold tracking-tight text-brand-text">UNIO</span>
          </Link>

          {/* Desktop Nav Links */}
          <div className="relative z-10 hidden md:flex items-center gap-7 text-sm font-medium text-brand-muted">
            <button
              type="button"
              onClick={() => scrollToSection('hero')}
              className="hover:text-brand-blue transition-colors cursor-pointer"
            >
              Home
            </button>
            <button
              type="button"
              onClick={() => scrollToSection('about')}
              className="hover:text-brand-blue transition-colors cursor-pointer"
            >
              About UNIO
            </button>
            <button
              type="button"
              onClick={() => scrollToSection('innovation')}
              className="hover:text-brand-blue transition-colors cursor-pointer"
            >
              Innovation
            </button>
            <button
              type="button"
              onClick={() => scrollToSection('connected-campus')}
              className="hover:text-brand-blue transition-colors cursor-pointer"
            >
              Campus Intelligence
            </button>
          </div>

          {/* Desktop Right CTAs */}
          <div className="relative z-10 hidden sm:flex items-center gap-3">
            <Link
              to="/login"
              className="px-4 py-2 text-sm font-semibold text-brand-text hover:text-brand-blue transition-colors rounded-full"
            >
              Login
            </Link>
            <Link
              to="/login"
              className="glass-button glass-button-primary inline-flex items-center gap-1.5 px-5 py-2 rounded-full text-sm font-medium cursor-pointer"
            >
              <span className="button-text relative z-10 flex items-center gap-1.5">
                <span>Get Started</span>
                <ChevronRight aria-hidden="true" className="size-4" />
              </span>
              <div className="button-shine" />
            </Link>
          </div>

          {/* Mobile Menu Button */}
          <button
            type="button"
            aria-label={mobileMenuOpen ? 'Close Menu' : 'Open Menu'}
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="relative z-10 md:hidden p-2 text-brand-text hover:text-brand-blue rounded-full focus-visible:outline-2 focus-visible:outline-accent"
          >
            {mobileMenuOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>

        {/* Mobile Dropdown Drawer */}
        {mobileMenuOpen && (
          <div className="glass-capsule md:hidden absolute top-16 inset-x-4 max-w-md mx-auto rounded-3xl p-6 flex flex-col gap-4">
            <div className="button-shine" />
            <button
              type="button"
              onClick={() => scrollToSection('hero')}
              className="relative z-10 text-left py-2 font-medium text-brand-text hover:text-brand-blue border-b border-brand-border/60"
            >
              Home
            </button>
            <button
              type="button"
              onClick={() => scrollToSection('about')}
              className="relative z-10 text-left py-2 font-medium text-brand-text hover:text-brand-blue border-b border-brand-border/60"
            >
              About UNIO
            </button>
            <button
              type="button"
              onClick={() => scrollToSection('innovation')}
              className="relative z-10 text-left py-2 font-medium text-brand-text hover:text-brand-blue border-b border-brand-border/60"
            >
              Innovation
            </button>
            <button
              type="button"
              onClick={() => scrollToSection('connected-campus')}
              className="relative z-10 text-left py-2 font-medium text-brand-text hover:text-brand-blue border-b border-brand-border/60"
            >
              Campus Intelligence
            </button>
            <div className="relative z-10 pt-2 flex flex-col gap-2.5">
              <Link
                to="/login"
                className="w-full text-center py-2.5 rounded-full border border-brand-border text-sm font-semibold text-brand-text hover:bg-brand-pale"
              >
                Login
              </Link>
              <Link
                to="/login"
                className="glass-button glass-button-primary w-full text-center py-2.5 rounded-full text-sm font-semibold cursor-pointer"
              >
                <span className="button-text relative z-10 block">Get Started</span>
                <div className="button-shine" />
              </Link>
            </div>
          </div>
        )}
      </nav>

      {/* ── HERO SECTION ── */}
      <section
        id="hero"
        className="relative min-h-screen flex items-center justify-center overflow-hidden pt-28 pb-20 px-4 sm:px-6 lg:px-8"
      >
        {/* Background Cinematic Video */}
        <div className="absolute inset-0 z-0 overflow-hidden">
          <video
            autoPlay
            muted
            loop
            playsInline
            src="/assets/campus-hero.mp4"
            className="w-full h-full object-cover object-center pointer-events-none scale-105 transition-transform duration-1000"
          />
          {/* Subtle blue-toned cinematic overlay */}
          <div
            aria-hidden="true"
            className="absolute inset-0 bg-gradient-to-b from-brand-deep/35 via-brand-bg/25 to-brand-bg pointer-events-none"
          />
          <div
            aria-hidden="true"
            className="absolute inset-0 bg-radial from-transparent via-brand-bg/20 to-brand-bg/80 pointer-events-none"
          />
        </div>

        {/* Hero Content */}
        <div className="relative z-20 max-w-4xl mx-auto text-center flex flex-col items-center">
          {/* Main Heading */}
          <h1 className="text-4xl sm:text-6xl md:text-7xl font-bold tracking-tight text-brand-text leading-[1.08] mb-6 drop-shadow-xs">
            One Campus.
            <br />
            <span className="text-brand-blue">Every Operation.</span>
            <br />
            Intelligently Connected.
          </h1>

          {/* Supporting Text */}
          <p className="text-lg sm:text-xl text-brand-muted max-w-2xl mx-auto leading-relaxed mb-10">
            From infrastructure disruptions to campus-wide coordination, UNIO connects people, resources and operations
            through one intelligent platform.
          </p>

          {/* CTAs with Tactile Glassmorphism */}
          <div className="flex flex-col sm:flex-row items-center gap-5 w-full sm:w-auto">
            <button
              type="button"
              onClick={() => scrollToSection('about')}
              className="glass-button glass-button-primary w-full sm:w-auto inline-flex items-center justify-center px-8 py-3.5 rounded-full text-base font-semibold cursor-pointer"
            >
              <span className="button-text relative z-10 flex items-center justify-center gap-2">
                <span>Explore UNIO</span>
                <ArrowRight className="size-4" />
              </span>
              <div className="button-shine" />
            </button>
            <button
              type="button"
              onClick={() => navigate('/login')}
              className="glass-button w-full sm:w-auto inline-flex items-center justify-center px-8 py-3.5 rounded-full text-base font-semibold cursor-pointer"
            >
              <span className="button-text relative z-10 flex items-center justify-center gap-2 text-brand-text">
                <span>Access Platform</span>
                <ChevronRight className="size-4 text-brand-muted" />
              </span>
              <div className="button-shine" />
            </button>
          </div>
        </div>
      </section>

      {/* ── UNIO INTRODUCTION SECTION ── */}
      <section id="about" className="py-24 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto relative">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <p className="text-xs font-semibold tracking-wider uppercase text-brand-blue mb-3">Architected for Higher Education</p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight text-brand-text leading-tight mb-6">
            Beyond Campus Management.
            <br />
            <span className="text-brand-deep">Into Campus Intelligence.</span>
          </h2>
          <p className="text-base sm:text-lg text-brand-muted leading-relaxed">
            UNIO transforms disconnected campus operations into a coordinated intelligent ecosystem, helping
            institutions understand disruptions, evaluate consequences and make informed operational decisions.
          </p>
        </div>

        {/* Editorial 3-Column Pillars */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="rounded-3xl border border-brand-border/80 bg-white dark:bg-surface p-8 shadow-card flex flex-col justify-between">
            <div className="mb-6">
              <div className="size-12 rounded-2xl bg-brand-pale text-brand-blue flex items-center justify-center mb-5">
                <Network className="size-6" />
              </div>
              <h3 className="text-xl font-bold text-brand-text mb-3">Unified Spatial Truth</h3>
              <p className="text-sm text-brand-muted leading-relaxed">
                Connects architectural maps, electrical panels, network switches, and academic spaces into an immutable
                operational dependency model.
              </p>
            </div>
            <div className="pt-4 border-t border-brand-border/60 text-xs font-medium text-brand-blue flex items-center gap-1">
              <span>Zero data silos</span>
            </div>
          </div>

          <div className="rounded-3xl border border-brand-border/80 bg-white dark:bg-surface p-8 shadow-card flex flex-col justify-between">
            <div className="mb-6">
              <div className="size-12 rounded-2xl bg-brand-light text-brand-deep flex items-center justify-center mb-5">
                <Activity className="size-6" />
              </div>
              <h3 className="text-xl font-bold text-brand-text mb-3">Cascading Traceability</h3>
              <p className="text-sm text-brand-muted leading-relaxed">
                When a utility failure occurs, UNIO immediately charts every impacted room, exam, scheduled lecture, and
                lab session before reports even arrive.
              </p>
            </div>
            <div className="pt-4 border-t border-brand-border/60 text-xs font-medium text-brand-deep flex items-center gap-1">
              <span>Automated impact mapping</span>
            </div>
          </div>

          <div className="rounded-3xl border border-brand-border/80 bg-white dark:bg-surface p-8 shadow-card flex flex-col justify-between">
            <div className="mb-6">
              <div className="size-12 rounded-2xl bg-brand-pale text-brand-blue flex items-center justify-center mb-5">
                <ShieldCheck className="size-6" />
              </div>
              <h3 className="text-xl font-bold text-brand-text mb-3">Closed-Loop Recovery</h3>
              <p className="text-sm text-brand-muted leading-relaxed">
                Validates alternative halls, verifies parts inventory in the ledger, and routes dispatches to qualified
                technicians with full audit compliance.
              </p>
            </div>
            <div className="pt-4 border-t border-brand-border/60 text-xs font-medium text-brand-blue flex items-center gap-1">
              <span>Verified resolution protocol</span>
            </div>
          </div>
        </div>
      </section>

      {/* ── FOUR INNOVATION ENGINES ── */}
      <section id="innovation" className="py-24 px-4 sm:px-6 lg:px-8 bg-brand-pale/40 border-y border-brand-border/60">
        <div className="max-w-6xl mx-auto">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <p className="text-xs font-semibold tracking-wider uppercase text-brand-blue mb-3">Under the Hood</p>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-brand-text mb-4">
              Four Core Innovation Engines
            </h2>
            <p className="text-base text-brand-muted">
              Purpose-built operational engines designed to prevent collisions, isolate risks, and enforce institutional
              accuracy.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {INNOVATION_CARDS.map((card) => {
              const Icon = card.icon
              return (
                <div
                  key={card.number}
                  className="rounded-3xl border border-brand-border/90 bg-white dark:bg-surface p-8 sm:p-10 shadow-card hover:shadow-pop transition-all hover:-translate-y-1 relative overflow-hidden group"
                >
                  {/* Subtle top accent bar */}
                  <div className="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-brand-blue via-brand-deep to-brand-blue opacity-0 group-hover:opacity-100 transition-opacity" />

                  <div className="flex items-start justify-between mb-6">
                    <div className={cn('size-14 rounded-2xl border flex items-center justify-center', card.accent)}>
                      <Icon className="size-7" />
                    </div>
                    <span className="text-xs font-bold tracking-widest text-brand-muted/70 font-mono">
                      ENGINE {card.number}
                    </span>
                  </div>

                  <p className="text-xs font-bold uppercase tracking-wider text-brand-blue mb-1">{card.subtitle}</p>
                  <h3 className="text-2xl font-bold text-brand-text mb-4">{card.title}</h3>
                  <p className="text-sm sm:text-base text-brand-muted leading-relaxed">{card.description}</p>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* ── HOW UNIO WORKS (4-STAGE PROCESS) ── */}
      <section className="py-24 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <p className="text-xs font-semibold tracking-wider uppercase text-brand-blue mb-3">Operational Lifecycle</p>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-brand-text mb-4">How UNIO Works</h2>
          <p className="text-base text-brand-muted">
            From initial disruption trigger to verified resolution, every stage is guided by dependency awareness.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 relative">
          {WORKFLOW_STEPS.map((step) => {
            const Icon = step.icon
            return (
              <div
                key={step.step}
                className="rounded-3xl border border-brand-border/80 bg-white dark:bg-surface p-7 shadow-card relative flex flex-col justify-between group hover:border-brand-blue/40 transition-colors"
              >
                <div>
                  <div className="flex items-center justify-between mb-5">
                    <span className="inline-flex items-center justify-center size-8 rounded-full bg-brand-pale text-xs font-bold text-brand-blue font-mono">
                      {step.step}
                    </span>
                    <span className="text-xs font-semibold tracking-wider text-brand-deep uppercase">{step.tag}</span>
                  </div>
                  <div className="mb-4 text-brand-blue">
                    <Icon className="size-6" />
                  </div>
                  <h3 className="text-base font-bold text-brand-text mb-2">{step.title}</h3>
                  <p className="text-xs sm:text-sm text-brand-muted leading-relaxed">{step.description}</p>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {/* ── CONNECTED CAMPUS SECTION (WITH ACTUAL EASWARI SVG) ── */}
      <section id="connected-campus" className="py-24 px-4 sm:px-6 lg:px-8 bg-brand-pale/30 border-t border-brand-border/60">
        <div className="max-w-6xl mx-auto">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <p className="text-xs font-semibold tracking-wider uppercase text-brand-blue mb-3">Spatial Architecture</p>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight text-brand-text mb-6">
              Every Resource. One Connected Campus.
            </h2>
            <p className="text-base sm:text-lg text-brand-muted leading-relaxed">
              UNIO continuously links academic schedules, facilities, maintenance personnel, utility feeds and
              procurement pipelines into an active digital campus representation.
            </p>
          </div>

          {/* Interactive Connected Campus Map with SRM Easwari SVG */}
          <div className="rounded-3xl border border-brand-border/90 bg-white dark:bg-surface p-6 sm:p-8 shadow-pop mb-12">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6 pb-4 border-b border-brand-border/60">
              <div>
                <h3 className="text-lg font-bold text-brand-text">SRM Easwari Engineering College — Master Campus Map</h3>
                <p className="text-xs text-brand-muted">
                  Interactive spatial map powered by UNIO's precision vector geometry and real-time facility overlays.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                  <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Live Coordination
                </span>
              </div>
            </div>

            {/* Embedded CampusMap Component */}
            <div className="w-full h-112 rounded-2xl overflow-hidden border border-brand-border/80 bg-brand-bg relative">
              <CampusMap
                selectedId={selectedMapRegion}
                onSelect={(id) => setSelectedMapRegion(id)}
                className="w-full h-full"
              />
            </div>
            <p className="text-xs text-center text-brand-muted mt-3">
              Click any campus block or building on the map to inspect spatial coordination.
            </p>
          </div>

          {/* 8 Connected Resource Nodes */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {CONNECTED_DOMAINS.map((domain) => {
              const Icon = domain.icon
              return (
                <div
                  key={domain.label}
                  className="rounded-2xl border border-brand-border/70 bg-white dark:bg-surface p-5 shadow-xs hover:shadow-card transition-shadow flex flex-col justify-between"
                >
                  <div className="size-9 rounded-xl bg-brand-pale text-brand-blue flex items-center justify-center mb-3">
                    <Icon className="size-4.5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-brand-text mb-1">{domain.label}</h4>
                    <p className="text-xs text-brand-muted leading-tight">{domain.desc}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* ── FINAL CTA SECTION ── */}
      <section className="py-24 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto text-center">
        <div className="rounded-3xl border border-brand-blue/30 bg-gradient-to-b from-brand-light/50 via-white to-brand-pale/50 dark:from-surface-2 dark:to-surface p-10 sm:p-16 shadow-pop relative overflow-hidden">
          <div
            aria-hidden="true"
            className="absolute -top-24 -right-24 size-96 rounded-full bg-brand-light/60 blur-3xl pointer-events-none"
          />
          <div
            aria-hidden="true"
            className="absolute -bottom-24 -left-24 size-96 rounded-full bg-brand-lavender/60 blur-3xl pointer-events-none"
          />

          <div className="relative z-10 max-w-2xl mx-auto">
            <h2 className="text-3xl sm:text-5xl font-bold tracking-tight text-brand-text mb-4">
              Make Every Campus Operation Count.
            </h2>
            <p className="text-base sm:text-lg text-brand-muted mb-8 leading-relaxed">
              Bring campus operations, intelligence and coordination together with UNIO.
            </p>
            <Link
              to="/login"
              className="glass-button glass-button-primary inline-flex items-center justify-center px-9 py-4 rounded-full text-base font-semibold cursor-pointer"
            >
              <span className="button-text relative z-10 flex items-center justify-center gap-2">
                <span>Enter UNIO</span>
                <ArrowRight className="size-4.5" />
              </span>
              <div className="button-shine" />
            </Link>
          </div>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="border-t border-brand-border/80 bg-white dark:bg-surface py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2.5">
            <BrandMark className="size-6" />
            <span className="text-base font-bold tracking-tight text-brand-text">UNIO</span>
            <span className="text-xs text-brand-muted ml-2">Intelligent Campus Operations Platform</span>
          </div>

          <div className="flex items-center gap-6 text-xs sm:text-sm font-medium text-brand-muted">
            <button
              type="button"
              onClick={() => scrollToSection('about')}
              className="hover:text-brand-blue transition-colors cursor-pointer"
            >
              About
            </button>
            <button
              type="button"
              onClick={() => scrollToSection('connected-campus')}
              className="hover:text-brand-blue transition-colors cursor-pointer"
            >
              Platform
            </button>
            <button
              type="button"
              onClick={() => scrollToSection('innovation')}
              className="hover:text-brand-blue transition-colors cursor-pointer"
            >
              Innovation
            </button>
            <Link to="/login" className="hover:text-brand-blue transition-colors">
              Login
            </Link>
          </div>

          <p className="text-xs text-brand-muted/80">
            &copy; {new Date().getFullYear()} UNIO Campus Operations. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  )
}
