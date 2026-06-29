import RevealSection from "./RevealSection";

const STEPS = [
  { num: "01", who: "You",     title: "Drop source files",        desc: "Place .md, .txt, or README files into to_be_extracted/. PDFs work via Claude Code or Codex natively.", color: "var(--red)" },
  { num: "02", who: "Agent",   title: "Reads the files",          desc: "Claude Code, Codex, Copilot, or OpenCode reads your source files from the repo root.", color: "var(--fg)" },
  { num: "03", who: "Agent",   title: "Selects extraction skill", desc: "The agent reads the skills/ folder and picks Financial, Research, General, or Reconciliation.", color: "var(--fg)" },
  { num: "04", who: "Agent",   title: "Writes extraction JSON",   desc: "Entities, relationships, and chunks are written to extractions/{source}_extracted.json.", color: "var(--fg)" },
  { num: "05", who: "Agent",   title: "Calls MCP ingestion",      desc: "The agent calls ingest_from_file() on each validated extraction file via the MCP server.", color: "var(--fg)" },
  { num: "06", who: "Preciso", title: "Graph is ready",           desc: "Graph artifacts persist in GRAPH_IS_HERE/ — queryable immediately, reusable across sessions.", color: "var(--teal)" },
];

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="py-28 border-b-2 border-border bg-surface relative overflow-hidden">
      {/* Watermark number */}
      <div className="absolute right-0 top-0 font-barlow text-[320px] leading-none text-border select-none pointer-events-none opacity-40">
        06
      </div>

      <div className="relative z-10 max-w-6xl mx-auto px-6">
        <RevealSection>
          <p className="font-barlow text-sm uppercase tracking-[0.25em] text-[var(--red)] mb-4">Process</p>
          <h2 className="font-barlow text-[72px] sm:text-[96px] leading-[0.88] uppercase text-foreground mb-16">
            How it<br /><span className="text-[var(--red)]">works.</span>
          </h2>
        </RevealSection>

        <div className="space-y-2">
          {STEPS.map((step, i) => (
            <RevealSection key={step.num} delay={i * 60}>
              <div className="group flex items-stretch border-2 border-border hover:border-foreground transition-colors duration-200 bg-background hover:bg-card">
                {/* Step number */}
                <div className="shrink-0 w-20 flex items-center justify-center border-r-2 border-border group-hover:border-foreground transition-colors">
                  <span
                    className="font-barlow text-3xl text-border group-hover:text-[var(--red)] transition-colors duration-200"
                  >
                    {step.num}
                  </span>
                </div>

                {/* Content */}
                <div className="flex-1 px-6 py-5 flex items-center justify-between gap-4">
                  <div>
                    <p className="font-barlow text-2xl uppercase text-foreground">{step.title}</p>
                    <p className="text-sm text-muted mt-1 max-w-xl">{step.desc}</p>
                  </div>
                  <span
                    className="shrink-0 font-barlow text-sm uppercase tracking-widest px-3 py-1 border-2 font-black"
                    style={{ color: step.color, borderColor: step.color }}
                  >
                    {step.who}
                  </span>
                </div>
              </div>
            </RevealSection>
          ))}
        </div>

        {/* Folder contract — RED header bar */}
        <RevealSection delay={300} className="border-2 border-foreground mt-12 overflow-hidden">
          <div className="flex items-center gap-2 px-6 py-4 border-b-2 border-foreground bg-[var(--stripe)]">
            <span className="font-barlow text-lg uppercase tracking-widest text-[var(--stripe-text)]">
              Folder Contract
            </span>
          </div>
          <div className="p-6 font-mono text-sm space-y-2 bg-background">
            {[
              { path: "to_be_extracted/", desc: "drop your source files here (.md, .txt)", color: "var(--red)" },
              { path: "skills/",          desc: "agent reads these to know how to extract", color: "var(--amber)" },
              { path: "extractions/",     desc: "agent writes extraction JSON here",         color: "var(--teal)" },
              { path: "GRAPH_IS_HERE/",   desc: "graph artifacts — source of truth",          color: "var(--violet)" },
              { path: "docs/",            desc: "guides and architecture reference",           color: "var(--muted)" },
            ].map((item) => (
              <div key={item.path} className="flex items-baseline gap-4">
                <span className="w-44 shrink-0 font-bold" style={{ color: item.color }}>{item.path}</span>
                <span className="text-muted">← {item.desc}</span>
              </div>
            ))}
          </div>
        </RevealSection>
      </div>
    </section>
  );
}
