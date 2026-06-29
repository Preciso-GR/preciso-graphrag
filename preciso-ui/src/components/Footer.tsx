const LINKS = {
  Docs: [
    { label: "Getting Started", href: "https://github.com/Preciso-GR/preciso-graphrag/blob/main/docs/getting-started.md" },
    { label: "Skills Guide",    href: "https://github.com/Preciso-GR/preciso-graphrag/blob/main/docs/skills-guide.md" },
    { label: "Eval Guide",      href: "https://github.com/Preciso-GR/preciso-graphrag/blob/main/docs/eval-guide.md" },
    { label: "Architecture",    href: "https://github.com/Preciso-GR/preciso-graphrag/blob/main/docs/architecture.md" },
    { label: "FAQ",             href: "https://github.com/Preciso-GR/preciso-graphrag/blob/main/docs/faq.md" },
  ],
  Project: [
    { label: "GitHub",              href: "https://github.com/Preciso-GR/preciso-graphrag" },
    { label: "Contributing",        href: "https://github.com/Preciso-GR/preciso-graphrag/blob/main/CONTRIBUTING.md" },
    { label: "Issues",              href: "https://github.com/Preciso-GR/preciso-graphrag/issues" },
    { label: "License (Apache 2.0)", href: "https://github.com/Preciso-GR/preciso-graphrag/blob/main/LICENSE" },
  ],
  Exports: [
    { label: "Neo4j Export",   href: "https://github.com/Preciso-GR/preciso-graphrag/blob/main/docs/getting-started.md" },
    { label: "Qdrant Export",  href: "https://github.com/Preciso-GR/preciso-graphrag/blob/main/docs/getting-started.md" },
    { label: "GraphML Format", href: "https://github.com/Preciso-GR/preciso-graphrag/blob/main/docs/architecture.md" },
  ],
};

export default function Footer() {
  return (
    <footer className="bg-[var(--dark-strip)] text-[#F5EDE8]">
      {/* RED top accent line */}
      <div className="h-1 bg-[var(--stripe)]" />

      <div className="max-w-6xl mx-auto px-6 py-16">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-16">
          <div className="md:col-span-1">
            <p className="font-anton text-4xl text-[#F5EDE8] uppercase mb-4 tracking-tight">Preciso</p>
            <p className="text-sm text-[#7A5555] leading-relaxed mb-6">
              Precise knowledge graphs from your documents.
              Local-first. Agent-native. Open source.
            </p>
            <p className="text-xs text-[#4A3030] italic leading-relaxed">
              Named after Bruno Fernandes.<br />
              Every pass lands exactly where it needs to.
            </p>
            <div className="mt-6 inline-flex items-center gap-2 border border-[#4A3030] px-3 py-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#1D4ED8]" />
              <span className="text-xs font-mono text-[#4A3030] uppercase tracking-wider">Apache 2.0</span>
            </div>
          </div>

          {Object.entries(LINKS).map(([section, links]) => (
            <div key={section}>
              <p className="font-barlow text-xs uppercase tracking-[0.2em] text-[#4A3030] mb-5">{section}</p>
              <ul className="space-y-3">
                {links.map((link) => (
                  <li key={link.label}>
                    <a href={link.href} target="_blank" rel="noopener noreferrer"
                      className="text-sm text-[#7A5555] hover:text-[#F5EDE8] transition-colors duration-150">
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="border-t border-[#2A1515] pt-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <p className="text-xs font-mono text-[#4A3030]">
            © {new Date().getFullYear()} Preciso · Open source · Apache 2.0
          </p>
          <p className="font-barlow text-lg uppercase text-[#2A1515] tracking-wide">
            Every pass lands exactly where it needs to.
          </p>
        </div>
      </div>
    </footer>
  );
}
