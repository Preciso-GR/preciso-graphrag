import RevealSection from "./RevealSection";

export default function ComparisonSection() {
  return (
    <section id="why" className="py-28 border-b-2 border-border bg-background relative overflow-hidden">
      <div className="max-w-6xl mx-auto px-6">

        <RevealSection>
          <p className="font-barlow text-sm uppercase tracking-[0.25em] text-[var(--red)] mb-4">Why GraphRAG</p>
          <h2 className="font-barlow text-[72px] sm:text-[96px] leading-[0.88] uppercase text-foreground mb-4">
            Graph<span className="text-outline-dark">RAG</span>
            <br />beats regular
            <br /><span className="text-[var(--red)]">RAG.</span>
          </h2>
          <p className="text-muted text-lg max-w-lg mt-6 mb-16">
            Regular RAG retrieves chunks. Preciso traverses connections — so your agent
            reasons across the graph, not just finds similar text.
          </p>
        </RevealSection>

        {/* Comparison grid */}
        <div className="grid md:grid-cols-2 gap-0 border-2 border-foreground">

          {/* ── Regular RAG ── dark header = equally treated, different accent */}
          <RevealSection delay={0} className="border-r-2 border-foreground">
            <div className="border-b-2 border-foreground px-6 py-4 flex items-center gap-2 bg-foreground">
              <span className="w-2 h-2 rounded-full bg-muted" />
              <span className="font-barlow text-xl uppercase tracking-wide text-background">Regular RAG</span>
              <span className="ml-auto text-xs font-mono text-muted">~19% accuracy</span>
            </div>
            <div className="p-6 space-y-5 bg-surface">
              <p className="font-mono text-sm text-muted">
                <span className="text-border">query: </span>
                &quot;What are Apple&apos;s risk factors and which executives manage them?&quot;
              </p>
              <div className="h-px bg-border" />
              <div className="space-y-2 text-sm text-muted font-mono">
                <p><span className="text-border">step 1:</span> embed query</p>
                <p><span className="text-border">step 2:</span> cosine similarity search</p>
                <p><span className="text-border">step 3:</span> return top-k chunks</p>
              </div>
              <div className="border border-border p-4 text-sm font-mono bg-background">
                <p className="text-[10px] text-muted uppercase tracking-wider mb-2">→ result</p>
                <p className="text-muted">Returns the Risk Factors section text.</p>
                <p className="text-muted mt-1">No entity linkage. No executive context.</p>
                <p className="mt-2 text-border font-mono">Multi-hop reasoning: ✗</p>
              </div>
            </div>
          </RevealSection>

          {/* ── Preciso ── red header */}
          <RevealSection delay={150}>
            <div className="border-b-2 border-foreground px-6 py-4 flex items-center justify-between bg-[var(--red)]">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[var(--stripe-text)]" />
                <span className="font-barlow text-xl uppercase tracking-wide text-[var(--stripe-text)]">Preciso</span>
              </div>
              <span className="text-xs font-mono text-[var(--stripe-text)]/70 bg-[var(--stripe-text)]/10 px-2 py-0.5">
                95.4% accuracy
              </span>
            </div>
            <div className="p-6 space-y-5 bg-background">
              <p className="font-mono text-sm text-muted">
                <span className="text-border">query: </span>
                &quot;What are Apple&apos;s risk factors and which executives manage them?&quot;
              </p>
              <div className="h-px bg-border" />
              <div className="space-y-2 text-sm text-foreground font-mono">
                <p><span className="text-[var(--red)] font-bold">→</span> traverse RISK_FACTOR nodes</p>
                <p><span className="text-[var(--red)] font-bold">→</span> follow EXPOSED_TO → COMPANY</p>
                <p><span className="text-[var(--red)] font-bold">→</span> follow EMPLOYS → PERSON</p>
                <p><span className="text-[var(--red)] font-bold">→</span> follow MANAGES → RISK_FACTOR</p>
              </div>
              <div className="border-2 border-[var(--red)] p-4 text-sm font-mono">
                <p className="text-[10px] text-[var(--red)] uppercase tracking-wider mb-2">→ result</p>
                <p className="text-foreground font-semibold">Supply Chain Risk · Tim Cook · MANAGES</p>
                <p className="text-foreground font-semibold">Regulatory Risk · Jeff Williams · OVERSEES</p>
                <p className="mt-2 text-[var(--teal)] font-bold">Multi-hop reasoning: ✓</p>
              </div>
            </div>
          </RevealSection>
        </div>

        {/* Bottom callout — RED stripe (per user: head bars = theme red) */}
        <RevealSection delay={200} className="border-2 border-t-0 border-foreground">
          <div className="bg-[var(--stripe)] text-[var(--stripe-text)] px-8 py-6 flex flex-col sm:flex-row items-start sm:items-center gap-4">
            <p className="flex-1 font-barlow text-2xl uppercase text-[var(--stripe-text)]">
              The graph makes multi-hop reasoning possible.
            </p>
            <a
              href="#how-it-works"
              className="shrink-0 font-barlow text-lg uppercase tracking-wide text-[var(--stripe-text)] hover:opacity-70 transition-opacity flex items-center gap-1"
            >
              See how it works →
            </a>
          </div>
        </RevealSection>
      </div>
    </section>
  );
}
