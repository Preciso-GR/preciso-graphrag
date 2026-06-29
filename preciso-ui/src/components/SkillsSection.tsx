import RevealSection from "./RevealSection";

const SKILLS = [
  { name: "Financial",       path: "skills/Financial-Graph-Extraction/",              color: "#8B1A1A", useWhen: "10-Ks, 10-Qs, earnings calls, analyst reports",              entities: ["COMPANY","PERSON","RISK_FACTOR","METRIC","SEGMENT"] },
  { name: "Research",        path: "skills/Research-paper-graph-extraction-skill/",   color: "#1D4ED8", useWhen: "Research papers, scientific literature, academic corpora",    entities: ["PAPER","AUTHOR","METHOD","DATASET","RESULT"] },
  { name: "General",         path: "skills/General-graph-extraction-skill/",          color: "#00A896", useWhen: "Codebases, READMEs, wikis, internal docs",                   entities: ["CONCEPT","MODULE","FUNCTION","DEPENDENCY","PERSON"] },
  { name: "Reconciliation",  path: "skills/Reconciliation-Subagent-Skill/",           color: "#7C3AED", useWhen: "Cleanup of existing extraction JSON — not for initial extraction", entities: ["MERGE","DEDUPE","VALIDATE","CONFLICT"] },
];

export default function SkillsSection() {
  return (
    <section id="skills" className="py-28 border-b-2 border-border bg-background">
      <div className="max-w-6xl mx-auto px-6">

        <RevealSection>
          <p className="font-barlow text-sm uppercase tracking-[0.25em] text-[var(--red)] mb-4">Skills</p>
          <h2 className="font-barlow text-[72px] sm:text-[96px] leading-[0.88] uppercase text-foreground mb-16">
            Domain-specific<br /><span className="text-[var(--red)]">extraction.</span>
          </h2>
        </RevealSection>

        <div className="grid sm:grid-cols-2 gap-0 border-2 border-foreground">
          {SKILLS.map((skill, i) => (
            <RevealSection
              key={skill.name}
              delay={i * 80}
              className={[
                "border-foreground",
                i % 2 === 0 ? "border-r-2" : "",
                i < 2 ? "border-b-2" : "",
              ].join(" ")}
            >
              <div className="h-full p-8 hover:bg-card bg-background transition-colors duration-200 group">
                <div className="mb-6">
                  <p className="font-barlow text-5xl uppercase leading-none mb-1" style={{ color: skill.color }}>
                    {skill.name}
                  </p>
                  <p className="text-xs font-mono text-muted truncate">{skill.path}SKILL.md</p>
                </div>
                <div className="mb-5">
                  <p className="text-[10px] font-mono uppercase tracking-widest text-muted mb-1.5">Use when</p>
                  <p className="text-sm text-foreground">{skill.useWhen}</p>
                </div>
                <div>
                  <p className="text-[10px] font-mono uppercase tracking-widest text-muted mb-2">Entity types</p>
                  <div className="flex flex-wrap gap-1.5">
                    {skill.entities.map((e) => (
                      <span key={e} className="text-[10px] font-mono font-bold px-2 py-0.5 border"
                        style={{ color: skill.color, borderColor: skill.color, backgroundColor: skill.color + "12" }}>
                        {e}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </RevealSection>
          ))}
        </div>

        {/* CTA bar — RED */}
        <RevealSection delay={300} className="border-2 border-t-0 border-foreground bg-[var(--stripe)] px-8 py-5 flex items-center justify-between">
          <p className="text-[var(--stripe-text)] text-sm font-mono opacity-70">Write and contribute your own skill</p>
          <a href="https://github.com/Preciso-GR/preciso-graphrag/blob/main/CONTRIBUTING.md" target="_blank" rel="noopener noreferrer"
            className="font-barlow text-lg uppercase tracking-wide text-[var(--stripe-text)] hover:opacity-70 transition-opacity">
            Contributing Guide →
          </a>
        </RevealSection>
      </div>
    </section>
  );
}
