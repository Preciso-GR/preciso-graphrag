'use client';
import { useState, useEffect } from 'react';
import type { ParsedGraph, QueryRun } from '@/lib/graph-types';
import { streamOpenAI, streamCohere, SYSTEM_PROMPT, buildContextString } from '@/lib/llm-providers';

interface Props {
  graph: ParsedGraph | null;
  contextNodeIds: string[];
  onRemoveContext: (id: string) => void;
  onCitationClick: (id: string) => void;
  onCitedNodesChange: (ids: string[]) => void;
}

const OPENAI_MODELS = ['gpt-4o-mini', 'gpt-4o', 'o1-mini'];
const COHERE_MODELS = ['command-r', 'command-r-plus'];

function parseCitations(text: string): string[] {
  const matches = text.match(/\[n\d+\]/g) || [];
  return [...new Set(matches.map(m => m.slice(1, -1)))];
}

function renderWithCitations(text: string, onCite: (id: string) => void) {
  const parts = text.split(/(\[n\d+\])/g);
  return parts.map((part, i) => {
    const match = part.match(/^\[n(\d+)\]$/);
    if (match) {
      const id = `n${match[1]}`;
      return (
        <button key={i} onClick={() => onCite(id)}
          className="inline-flex items-center px-1 py-0.5 mx-0.5 text-[10px] font-mono border rounded"
          style={{ color: 'var(--stripe)', borderColor: 'var(--stripe)', background: 'color-mix(in srgb, var(--stripe) 8%, transparent)' }}>
          {part}
        </button>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

const SectionHeader = ({ title, count }: { title: string; count?: number }) => (
  <div className="px-4 py-2 border-b font-mono text-xs uppercase tracking-widest"
    style={{ color: 'var(--fg)', borderColor: 'var(--border)' }}>
    {title}{count !== undefined && <span className="ml-1.5 opacity-50">({count})</span>}
  </div>
);

const Divider = () => (
  <div className="border-t" style={{ borderColor: 'var(--border)' }} />
);

export function WorkbenchPanel({ graph, contextNodeIds, onRemoveContext, onCitationClick, onCitedNodesChange }: Props) {
  const [provider, setProvider] = useState<'openai' | 'cohere'>('openai');
  const [model, setModel] = useState('gpt-4o-mini');
  const [apiKey, setApiKey] = useState('');
  const [editingKey, setEditingKey] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [response, setResponse] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState<QueryRun[]>([]);

  // Load API key from localStorage
  useEffect(() => {
    const key = localStorage.getItem(`preciso.${provider}_key`) || '';
    setApiKey(key);
    setModel(provider === 'openai' ? 'gpt-4o-mini' : 'command-r');
  }, [provider]);

  const contextNodes = graph ? graph.nodes.filter(n => contextNodeIds.includes(n.id)) : [];

  async function runQuery() {
    if (!prompt.trim() || !apiKey || !graph) return;
    setStreaming(true);
    setResponse('');
    setError('');

    const context = buildContextString(graph, contextNodeIds);
    const userMsg = `${context}\n\nQUESTION: ${prompt}`;
    let fullResponse = '';

    try {
      const stream = provider === 'openai'
        ? streamOpenAI({ apiKey, model, system: SYSTEM_PROMPT, user: userMsg })
        : streamCohere({ apiKey, model, system: SYSTEM_PROMPT, user: userMsg });

      for await (const chunk of stream) {
        fullResponse += chunk;
        setResponse(fullResponse);
      }

      const cited = parseCitations(fullResponse);
      onCitedNodesChange(cited);

      setHistory(prev => [{
        id: crypto.randomUUID(),
        timestamp: Date.now(),
        prompt,
        contextNodeIds: [...contextNodeIds],
        response: fullResponse,
        citedNodeIds: cited,
        provider,
        model,
      }, ...prev].slice(0, 10));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Query failed');
    } finally {
      setStreaming(false);
    }
  }

  function loadHistoryItem(item: QueryRun) {
    setPrompt(item.prompt);
    setResponse(item.response);
    onCitedNodesChange(item.citedNodeIds);
  }

  const models = provider === 'openai' ? OPENAI_MODELS : COHERE_MODELS;

  return (
    <div className="flex-1 flex flex-col overflow-y-auto text-sm" style={{ color: 'var(--fg)' }}>
      {/* Run Config */}
      <SectionHeader title="Run Config" />
      <div className="px-4 py-3 space-y-2 font-mono text-xs">
        <div className="flex items-center gap-2">
          <span style={{ color: 'var(--muted)', width: 80 }}>Provider</span>
          <select value={provider} onChange={e => setProvider(e.target.value as 'openai' | 'cohere')}
            className="flex-1 px-2 py-1 border text-xs font-mono"
            style={{ background: 'var(--bg)', color: 'var(--fg)', borderColor: 'var(--border)' }}>
            <option value="openai">OpenAI</option>
            <option value="cohere">Cohere</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span style={{ color: 'var(--muted)', width: 80 }}>Model</span>
          <select value={model} onChange={e => setModel(e.target.value)}
            className="flex-1 px-2 py-1 border text-xs font-mono"
            style={{ background: 'var(--bg)', color: 'var(--fg)', borderColor: 'var(--border)' }}>
            {models.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span style={{ color: 'var(--muted)', width: 80 }}>API key</span>
          {editingKey ? (
            <input type="password" value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              onBlur={() => { setEditingKey(false); localStorage.setItem(`preciso.${provider}_key`, apiKey); }}
              autoFocus
              className="flex-1 px-2 py-1 border text-xs font-mono"
              style={{ background: 'var(--bg)', color: 'var(--fg)', borderColor: 'var(--stripe)' }}
              placeholder={`${provider === 'openai' ? 'sk-...' : 'your-cohere-key'}`} />
          ) : (
            <div className="flex-1 flex items-center gap-2">
              <span style={{ color: apiKey ? 'var(--fg)' : 'var(--muted)' }}>
                {apiKey ? '•'.repeat(Math.min(12, apiKey.length)) : 'Not set'}
              </span>
              <button onClick={() => setEditingKey(true)} style={{ color: 'var(--muted)' }} className="hover:text-[var(--fg)]">
                ✎
              </button>
            </div>
          )}
        </div>
        <p style={{ color: 'var(--muted)', opacity: 0.6, fontSize: 10 }}>Key stays in browser. Never sent to Preciso servers.</p>
      </div>

      <Divider />

      {/* Context */}
      <SectionHeader title="Context" count={contextNodeIds.length} />
      <div className="px-4 py-3 flex flex-wrap gap-2">
        {contextNodes.length === 0 ? (
          <p className="text-xs font-mono" style={{ color: 'var(--muted)' }}>Click a node on the graph to add context</p>
        ) : contextNodes.map(n => (
          <div key={n.id} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-mono"
            style={{ borderColor: 'var(--border)', background: 'var(--bg)', color: 'var(--fg)' }}>
            <span className="w-1.5 h-1.5 rounded-full border" style={{ borderColor: 'var(--fg)', background: 'var(--bg)' }} />
            <span className="truncate max-w-[160px]">{n.label}</span>
            <button onClick={() => onRemoveContext(n.id)} className="ml-1 hover:opacity-100 opacity-50">×</button>
          </div>
        ))}
      </div>

      <Divider />

      {/* Prompt */}
      <SectionHeader title="Prompt" />
      <div className="px-4 py-3 flex flex-col gap-2">
        <textarea
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) runQuery(); }}
          rows={4}
          placeholder="Ask a question about this graph…"
          className="w-full px-3 py-2 text-xs font-mono border resize-none focus:outline-none"
          style={{
            background: 'var(--bg)', color: 'var(--fg)',
            borderColor: 'var(--border)',
          }}
        />
        <button
          onClick={runQuery}
          disabled={streaming || !prompt.trim() || !apiKey || !graph}
          className="self-start px-4 py-2 text-xs font-mono transition-colors disabled:opacity-40"
          style={{ background: 'var(--stripe)', color: 'var(--stripe-text)' }}
        >
          {streaming ? 'Running…' : 'Run query → ⌘↵'}
        </button>
      </div>

      <Divider />

      {/* Response */}
      <SectionHeader title="Response" />
      <div className="px-4 py-3 font-mono text-xs leading-relaxed min-h-[80px]">
        {error ? (
          <p style={{ color: 'var(--red-bright)' }}>{error}</p>
        ) : response ? (
          <div className="space-y-2">
            <p style={{ color: 'var(--fg)' }}>{renderWithCitations(response, onCitationClick)}</p>
            <div className="flex gap-2 mt-3">
              <button onClick={() => navigator.clipboard.writeText(response)}
                className="px-2 py-1 border text-xs font-mono hover:bg-[var(--surface)]"
                style={{ borderColor: 'var(--border)' }}>
                ⟲ Copy
              </button>
            </div>
          </div>
        ) : (
          <p style={{ color: 'var(--muted)' }}>{graph ? 'Set an API key, add context, and run a query.' : 'Load a graph first.'}</p>
        )}
      </div>

      <Divider />

      {/* History */}
      <SectionHeader title="History" count={history.length} />
      <div className="px-4 py-3 space-y-1 font-mono text-xs">
        {history.length === 0 ? (
          <p style={{ color: 'var(--muted)' }}>No queries yet this session</p>
        ) : (
          <>
            {history.map(item => (
              <button key={item.id} onClick={() => loadHistoryItem(item)}
                className="w-full text-left py-1.5 flex items-start gap-2 hover:bg-[var(--surface)] px-2 -mx-2 rounded transition-colors">
                <span style={{ color: 'var(--muted)' }}>·</span>
                <span className="flex-1 truncate" style={{ color: 'var(--fg)' }}>{item.prompt}</span>
                <span style={{ color: 'var(--muted)', opacity: 0.6, fontSize: 10, flexShrink: 0 }}>
                  {Math.round((Date.now() - item.timestamp) / 60000)}m ago
                </span>
              </button>
            ))}
            <button onClick={() => setHistory([])}
              className="mt-2 text-xs font-mono"
              style={{ color: 'var(--muted)' }}>
              Clear history
            </button>
          </>
        )}
      </div>
    </div>
  );
}
