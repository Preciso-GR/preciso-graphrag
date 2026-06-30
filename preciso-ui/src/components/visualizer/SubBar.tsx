'use client';
import { useRef } from 'react';
import type { ParsedGraph } from '@/lib/graph-types';
import { parseGraphML } from '@/lib/graphml-parser';

interface Props {
  graph: ParsedGraph | null;
  onGraphLoaded: (g: ParsedGraph) => void;
  workbenchOpen: boolean;
  onToggleWorkbench: () => void;
}

export function SubBar({ graph, onGraphLoaded, workbenchOpen, onToggleWorkbench }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);

  function handleFile(file: File) {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const parsed = parseGraphML(e.target!.result as string, file.name.replace('.graphml', ''));
        onGraphLoaded(parsed);
      } catch (err) {
        console.error('Failed to parse GraphML:', err);
      }
    };
    reader.readAsText(file);
  }

  return (
    <div
      className="h-10 px-4 border-b flex items-center gap-3 font-mono text-xs text-[var(--muted)] shrink-0"
      style={{ borderColor: 'color-mix(in srgb, var(--muted) 20%, transparent)' }}
    >
      {graph ? (
        <>
          <span className="text-[var(--fg)]">Graph:</span>
          <span className="font-mono text-[var(--fg)]">{graph.metadata.sourceName || 'untitled'}</span>
          <span style={{ opacity: 0.4 }}>·</span>
          <span>{graph.metadata.nodeCount} nodes</span>
          <span style={{ opacity: 0.4 }}>·</span>
          <span>{graph.metadata.edgeCount} edges</span>
          <span style={{ opacity: 0.4 }}>·</span>
          <span>{Object.keys(graph.metadata.entityTypes).length} types</span>
        </>
      ) : (
        <span>No graph loaded — drop a .graphml file or load the sample</span>
      )}

      <div className="flex-1" />

      <input
        ref={fileRef}
        type="file"
        accept=".graphml,.xml"
        className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
      />
      <button
        onClick={() => fileRef.current?.click()}
        className="px-2 py-1 rounded hover:bg-[var(--surface)] transition-colors text-[var(--fg)]"
      >
        ⇪ Load .graphml
      </button>
      <button
        onClick={onToggleWorkbench}
        className="px-2 py-1 rounded hover:bg-[var(--surface)] transition-colors"
      >
        {workbenchOpen ? '⇄ Hide panel' : '⇄ Show panel'}
      </button>
    </div>
  );
}
