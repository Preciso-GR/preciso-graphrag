import type { ParsedGraph, GraphNode } from './graph-types';

export async function* streamOpenAI(opts: {
  apiKey: string; model: string; system: string; user: string;
}): AsyncGenerator<string> {
  const res = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${opts.apiKey}` },
    body: JSON.stringify({
      model: opts.model, stream: true,
      messages: [{ role: 'system', content: opts.system }, { role: 'user', content: opts.user }],
    }),
  });
  if (!res.ok) throw new Error(`OpenAI error ${res.status}: ${await res.text()}`);
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value);
    const lines = buffer.split('\n');
    buffer = lines.pop()!;
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const payload = line.slice(6).trim();
      if (payload === '[DONE]') return;
      try {
        const json = JSON.parse(payload);
        const delta = json.choices?.[0]?.delta?.content;
        if (delta) yield delta;
      } catch { /* skip */ }
    }
  }
}

export async function* streamCohere(opts: {
  apiKey: string; model: string; system: string; user: string;
}): AsyncGenerator<string> {
  const res = await fetch('https://api.cohere.ai/v1/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${opts.apiKey}` },
    body: JSON.stringify({
      model: opts.model, stream: true,
      preamble: opts.system,
      message: opts.user,
    }),
  });
  if (!res.ok) throw new Error(`Cohere error ${res.status}: ${await res.text()}`);
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value);
    const lines = buffer.split('\n');
    buffer = lines.pop()!;
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const json = JSON.parse(line);
        if (json.event_type === 'text-generation' && json.text) yield json.text;
      } catch { /* skip */ }
    }
  }
}

export const SYSTEM_PROMPT = `You are a knowledge graph reasoning assistant for Preciso. Answer using ONLY the provided graph context. Cite entity IDs inline using [n1] [n2] format matching the IDs in the context. Be concise. If the graph doesn't contain the answer, say so — do not speculate.`;

export function buildContextString(graph: ParsedGraph, contextNodeIds: string[]): string {
  const focal = contextNodeIds.length
    ? graph.nodes.filter((n) => contextNodeIds.includes(n.id))
    : [...graph.nodes].sort((a, b) => b.degree - a.degree).slice(0, 30);
  const focalIds = new Set(focal.map((n) => n.id));
  const neighborIds = new Set<string>();
  for (const e of graph.edges) {
    const s = typeof e.source === 'string' ? e.source : (e.source as GraphNode).id;
    const t = typeof e.target === 'string' ? e.target : (e.target as GraphNode).id;
    if (focalIds.has(s)) neighborIds.add(t);
    if (focalIds.has(t)) neighborIds.add(s);
  }
  const nodeMap = new Map(graph.nodes.map((n) => [n.id, n]));
  const allNodes = [...new Set([...focalIds, ...neighborIds])].map((id) => nodeMap.get(id)!).filter(Boolean);
  const allEdges = graph.edges.filter((e) => {
    const s = typeof e.source === 'string' ? e.source : (e.source as GraphNode).id;
    const t = typeof e.target === 'string' ? e.target : (e.target as GraphNode).id;
    return focalIds.has(s) || focalIds.has(t);
  });
  const entityLines = allNodes.map((n) => `[${n.id}] ${n.label} (${n.type}): ${n.description || '—'}`);
  const edgeLines = allEdges.map((e) => {
    const s = typeof e.source === 'string' ? e.source : (e.source as GraphNode).id;
    const t = typeof e.target === 'string' ? e.target : (e.target as GraphNode).id;
    return `[${s}] --[${e.label || 'related'}]--> [${t}]`;
  });
  return `ENTITIES:\n${entityLines.join('\n')}\n\nRELATIONSHIPS:\n${edgeLines.join('\n')}`;
}
