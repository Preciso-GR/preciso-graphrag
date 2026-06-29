import RevealSection from "./RevealSection";

const STEPS = [
  {
    num: "01", title: "Clone and install",
    code: `git clone https://github.com/Preciso-GR/preciso-graphrag
cd preciso-graphrag
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt`,
    note: "Requires Python 3.11+. Open agent from repo root.",
  },
  {
    num: "02", title: "Drop files into to_be_extracted/",
    code: `cp my-10k.md to_be_extracted/
cp research-paper.md to_be_extracted/
cp internal-docs.txt to_be_extracted/`,
    note: "Best inputs: .md, .txt, README files, wiki exports.",
  },
  {
    num: "03", title: "Run this prompt in your agent",
    code: `Call get_server_status().
If overall is ready, proceed.
Read the files in to_be_extracted/.
Choose the most appropriate extraction skill.
Extract, validate, then call ingest_from_file.
Confirm graph artifacts in GRAPH_IS_HERE/.`,
    note: "Works with Claude Code, Codex, GitHub Copilot, and OpenCode.",
  },
];

const AGENTS = [
  { name: "Claude Code",    color: "#8B1A1A" },
  { name: "Codex",          color: "#059669" },
  { name: "GitHub Copilot", color: "var(--fg)" },
  { name: "OpenCode",       color: "#7C3AED" },
];

export default function QuickstartSection() {
  return (
    <section id="quickstart" className="py-28 bg-background">
      <div className="max-w-6xl mx-auto px-6">

        <RevealSection>
          <p className="font-barlow text-sm uppercase tracking-[0.25em] text-[var(--red)] mb-4">Quickstart</p>
          <h2 className="font-barlow text-[72px] sm:text-[96px] leading-[0.88] uppercase text-foreground mb-6">
            Up in<br /><span className="text-[var(--red)]">3 minutes.</span>
          </h2>
          <p className="text-muted text-lg max-w-lg mb-8">No pipeline. No cloud. No config.</p>
          <div className="flex flex-wrap gap-2 mb-16">
            {AGENTS.map((a) => (
              <span key={a.name} className="font-barlow text-sm uppercase tracking-wide px-4 py-1.5 border-2 font-black"
                style={{ color: a.color, borderColor: a.color }}>
                {a.name}
              </span>
            ))}
          </div>
        </RevealSection>

        <div className="border-2 border-foreground">
          {STEPS.map((step, i) => (
            <RevealSection key={step.num} delay={i * 100} className={i < STEPS.length - 1 ? "border-b-2 border-foreground" : ""}>
              <div className="flex">
                {/* Step num — RED stripe header */}
                <div className="shrink-0 w-20 border-r-2 border-foreground flex items-start justify-center pt-6 bg-[var(--stripe)]">
                  <span className="font-barlow text-3xl text-[var(--stripe-text)]">{step.num}</span>
                </div>
                <div className="flex-1">
                  <div className="border-b-2 border-border px-6 py-3 bg-surface">
                    <p className="font-barlow text-xl uppercase text-foreground">{step.title}</p>
                  </div>
                  <pre className="px-6 py-5 text-sm font-mono text-muted overflow-x-auto whitespace-pre-wrap leading-relaxed bg-background">
                    <code>{step.code}</code>
                  </pre>
                  {step.note && (
                    <p className="px-6 pb-4 text-xs text-muted font-mono flex items-start gap-1.5">
                      <span className="text-[var(--red)] mt-0.5">›</span>{step.note}
                    </p>
                  )}
                </div>
              </div>
            </RevealSection>
          ))}
        </div>

        {/* Query examples — RED header */}
        <RevealSection delay={300} className="border-2 border-t-0 border-foreground overflow-hidden">
          <div className="border-b-2 border-foreground bg-[var(--stripe)] px-6 py-3">
            <p className="text-xs font-mono text-[var(--stripe-text)] uppercase tracking-widest">After ingestion, query your graph</p>
          </div>
          <div className="bg-[var(--dark-strip)] p-6 space-y-2">
            {[
              `"What are Apple's top 5 disclosed risk factors?"`,
              `"Which executives are connected to the supply chain risks?"`,
              `"What metrics declined year over year?"`,
            ].map((q) => (
              <p key={q} className="font-mono text-sm text-[var(--teal)]">
                <span className="text-[#4A3A3A]">› </span>{q}
              </p>
            ))}
          </div>
        </RevealSection>
      </div>
    </section>
  );
}
