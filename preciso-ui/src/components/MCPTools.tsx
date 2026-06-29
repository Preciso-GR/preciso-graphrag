import RevealSection from "./RevealSection";

const TOOLS = [
  { name: "get_server_status",              desc: "Runtime health check — call this before anything. Reports embedding mode, graph health, and LLM config.", priority: true },
  { name: "ingest_from_file",               desc: "Ingest a completed extraction JSON file from the extractions/ folder.", priority: false },
  { name: "reingest_from_file",             desc: "Retry ingestion without re-extracting. Useful after reconciliation.", priority: false },
  { name: "ingest_graph_tool",              desc: "Ingest an inline extraction payload directly — no file needed.", priority: false },
  { name: "ingest_with_reconciliation_tool", desc: "Ingest after reconciliation subagents finish. Handles merge conflicts.", priority: false },
  { name: "query_graph_tool",               desc: "Query the persisted graph. Returns entity + relationship context.", priority: false },
  { name: "export_graph_to_neo4j",          desc: "Optional: push graph structure to Neo4j. Local graph stays source of truth.", priority: false },
  { name: "export_vectors_to_qdrant",       desc: "Optional: push vector artifacts to Qdrant. Re-export when ready.", priority: false },
];

export default function MCPTools() {
  return (
    <section id="mcp-tools" className="py-28 border-b-2 border-border bg-surface">
      <div className="max-w-6xl mx-auto px-6">

        <RevealSection>
          <p className="font-barlow text-sm uppercase tracking-[0.25em] text-[var(--red)] mb-4">MCP Tools</p>
          <h2 className="font-barlow text-[72px] sm:text-[96px] leading-[0.88] uppercase text-foreground mb-6">
            Eight tools.<br /><span className="text-[var(--red)]">Plug in, use.</span>
          </h2>
          <p className="text-muted text-lg max-w-lg mb-16">
            The MCP server exposes a clean tool surface. Your agent calls them directly —
            no SDK wrappers, no config layers.
          </p>
        </RevealSection>

        {/* .mcp.json snippet — RED header bar */}
        <RevealSection className="border-2 border-foreground mb-6 overflow-hidden">
          <div className="flex items-center gap-2 px-5 py-3.5 border-b-2 border-foreground bg-[var(--stripe)]">
            <span className="text-xs font-mono text-[var(--stripe-text)] uppercase tracking-widest">.mcp.json</span>
          </div>
          <pre className="p-6 text-sm font-mono text-muted overflow-x-auto bg-background">
{`{
  "mcpServers": {
    "graphrag-mcp": {
      "type": "stdio",
      "command": "/bin/sh",
      "args": ["scripts/mcp_launcher.sh"],
      "cwd": ".",
      "tools": ["*"]
    }
  }
}`}
          </pre>
        </RevealSection>

        {/* Tool grid — ALL tools get equal treatment */}
        <div className="grid sm:grid-cols-2 gap-0 border-2 border-foreground">
          {TOOLS.map((tool, i) => (
            <RevealSection
              key={tool.name}
              delay={i * 50}
              className={[
                "border-foreground",
                i % 2 === 0 ? "border-r-2" : "",
                i < TOOLS.length - 2 ? "border-b-2" : "",
              ].join(" ")}
            >
              <div className="p-6 h-full bg-background hover:bg-surface transition-colors duration-150 group">
                <div className="flex items-start gap-3">
                  {/* Thin red left-border accent for priority tool only */}
                  {tool.priority && (
                    <div className="shrink-0 w-0.5 self-stretch bg-[var(--red)] mt-0.5" />
                  )}
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <p className="font-mono text-sm font-bold text-foreground">
                        {tool.name}()
                      </p>
                      {tool.priority && (
                        <span className="text-[10px] font-mono uppercase tracking-widest text-[var(--red)] border border-[var(--red)] px-1.5 py-0.5">
                          Call first
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-muted">{tool.desc}</p>
                  </div>
                </div>
              </div>
            </RevealSection>
          ))}
        </div>
      </div>
    </section>
  );
}
