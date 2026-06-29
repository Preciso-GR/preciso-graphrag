import GraphAnimation from "./GraphAnimation";

const WATERMARK_WORDS = Array(30).fill("PRECISO");

export default function Hero() {
  return (
    <section className="relative min-h-screen flex flex-col overflow-hidden bg-background">
      {/* Oversized watermark */}
      <div className="watermark-bg">{WATERMARK_WORDS.map((w, i) => <span key={i}>&nbsp;{w}&nbsp;</span>)}</div>
      <div className="absolute inset-0 dot-grid opacity-30 pointer-events-none z-[1]" />

      <div className="relative z-10 flex-1 flex flex-col max-w-6xl mx-auto px-6 pt-28 pb-16 w-full">

        {/* Marquee */}
        <div className="overflow-hidden mb-12">
          <div className="marquee-track">
            {Array(6).fill(null).map((_, i) => (
              <span key={i} className="flex items-center gap-6 pr-6">
                {["GraphRAG","Local-first","Zero hallucinations","Apache 2.0","MCP Native","95 / 100"].map((t) => (
                  <span key={t} className="flex items-center gap-2 text-xs font-mono text-muted uppercase tracking-widest whitespace-nowrap">
                    <span className="w-1 h-1 rounded-full bg-[var(--red)]" />
                    {t}
                  </span>
                ))}
              </span>
            ))}
          </div>
        </div>

        {/* Hero grid */}
        <div className="grid lg:grid-cols-2 gap-12 items-center flex-1">
          {/* Left */}
          <div>
            <h1 className="font-barlow text-[80px] sm:text-[100px] lg:text-[112px] leading-[0.9] uppercase tracking-tight mb-8">
              <span className="block text-foreground">Precise</span>
              <span className="block text-outline-red">Knowledge</span>
              <span className="block text-[var(--red)]">Graphs.</span>
            </h1>

            <p className="animate-fade-in-up delay-100 text-lg text-muted leading-relaxed mb-10 max-w-md">
              Drop files in. Your agent extracts entities and relationships, builds a
              queryable knowledge graph — locally. No cloud, no pipeline, no config.
            </p>

            <div className="animate-fade-in-up delay-200 flex flex-wrap items-center gap-3">
              <a href="#quickstart" className="bg-[var(--red)] hover:bg-[var(--red-bright)] text-[var(--stripe-text)] font-barlow font-black text-lg px-8 py-3 uppercase tracking-wide transition-colors flex items-center gap-2">
                Get Started <span>→</span>
              </a>
              <a href="https://github.com/Preciso-GR/preciso-graphrag" target="_blank" rel="noopener noreferrer"
                className="border-2 border-foreground hover:bg-foreground hover:text-background text-foreground font-barlow font-black text-lg px-8 py-3 uppercase tracking-wide transition-colors flex items-center gap-2">
                <GitHubIcon /> GitHub
              </a>
            </div>

            <p className="animate-fade-in-up delay-300 mt-8 text-xs text-muted font-mono">
              Tested · Walmart FY2022 + FY2023 10-K · 23 multi-hop questions · 0 hallucinations
            </p>
          </div>

          {/* Right — dark frame always */}
          <div className="animate-fade-in-up delay-200 relative hidden lg:block">
            <div className="relative border-2 border-foreground bg-[#0D0D0D] overflow-hidden shadow-2xl" style={{ height: "480px" }}>
              <div className="flex items-center justify-between px-4 py-3 border-b border-[#262626]">
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-[#8B1A1A]/70" />
                  <span className="w-3 h-3 rounded-full bg-[#D97706]/60" />
                  <span className="w-3 h-3 rounded-full bg-[#00A896]/60" />
                </div>
                <span className="text-[10px] text-[#525252] font-mono tracking-widest uppercase">Preciso · Live Graph</span>
                <span className="text-[10px] text-[#8B1A1A] font-mono">● ready</span>
              </div>
              <div className="w-full" style={{ height: "436px" }}>
                <GraphAnimation />
              </div>
            </div>
            <div className="absolute -bottom-5 -left-6 bg-background border-2 border-foreground px-4 py-3 text-xs max-w-[260px] shadow-lg">
              <p className="text-muted font-mono mb-1 uppercase tracking-widest text-[10px]">Query</p>
              <p className="text-foreground font-mono font-semibold">&quot;Which executives manage Apple&apos;s supply chain risk?&quot;</p>
              <p className="mt-2 text-[var(--red)] font-mono font-bold">→ Tim Cook · MANAGES · Supply Chain</p>
            </div>
            <div className="absolute -top-2 -right-2 w-12 h-12 border-t-2 border-r-2 border-[var(--red)]" />
            <div className="absolute -bottom-2 -left-2 w-12 h-12 border-b-2 border-l-2 border-[var(--red)]" />
          </div>
        </div>

        {/* Bottom stats */}
        <div className="mt-16 border-t-2 border-border pt-8 grid grid-cols-2 sm:grid-cols-4 gap-6">
          {[
            { val: "95", unit: "/100", label: "Preciso Score" },
            { val: "100%", unit: "", label: "Faithfulness" },
            { val: "0", unit: "", label: "Hallucinations" },
            { val: "0", unit: "", label: "Failed Questions" },
          ].map((s) => (
            <div key={s.label}>
              <p className="font-barlow text-5xl leading-none text-foreground">
                {s.val}{s.unit && <span className="text-2xl text-muted">{s.unit}</span>}
              </p>
              <p className="mt-1 text-xs text-muted font-mono uppercase tracking-wider">{s.label}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function GitHubIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
    </svg>
  );
}
