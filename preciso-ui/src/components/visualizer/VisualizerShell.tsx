'use client';
import { useState } from 'react';
import type { ParsedGraph } from '@/lib/graph-types';
import { parseGraphML } from '@/lib/graphml-parser';
import { WALMART_SAMPLE } from '@/lib/sample-graphs';
import { SubBar } from './SubBar';
import { GraphCanvas } from './GraphCanvas';
import { WorkbenchPanel } from './WorkbenchPanel';
import { EntityLegendStrip } from './EntityLegendStrip';
import { EmptyState } from './EmptyState';

export function VisualizerShell() {
  const [graph, setGraph] = useState<ParsedGraph | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [contextNodeIds, setContextNodeIds] = useState<string[]>([]);
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());
  const [workbenchOpen, setWorkbenchOpen] = useState(true);
  const [legendOpen, setLegendOpen] = useState(true);
  const [citedNodeIds, setCitedNodeIds] = useState<string[]>([]);

  // Drag-and-drop anywhere on the shell
  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const parsed = parseGraphML(ev.target!.result as string, file.name.replace('.graphml', ''));
        setGraph(parsed);
        setSelectedNodeId(null);
        setContextNodeIds([]);
        setCitedNodeIds([]);
      } catch (err) { console.error(err); }
    };
    reader.readAsText(file);
  }

  function handleNodeClick(nodeId: string) {
    setSelectedNodeId(nodeId);
    setContextNodeIds(prev => prev.includes(nodeId) ? prev : [...prev, nodeId]);
  }

  function handleTypeToggle(type: string) {
    setHiddenTypes(prev => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type); else next.add(type);
      return next;
    });
  }

  function handleLoadSample() {
    setGraph(WALMART_SAMPLE);
    setSelectedNodeId(null);
    setContextNodeIds([]);
    setCitedNodeIds([]);
  }

  return (
    <div
      className="flex-1 flex flex-col overflow-hidden"
      style={{ background: 'var(--bg)' }}
      onDragOver={e => e.preventDefault()}
      onDrop={handleDrop}
    >
      <SubBar
        graph={graph}
        onGraphLoaded={(g) => { setGraph(g); setSelectedNodeId(null); setContextNodeIds([]); setCitedNodeIds([]); }}
        workbenchOpen={workbenchOpen}
        onToggleWorkbench={() => setWorkbenchOpen(v => !v)}
      />

      <div className="flex-1 flex overflow-hidden">
        <main className="flex-1 relative overflow-hidden">
          {graph ? (
            <GraphCanvas
              graph={graph}
              selectedNodeId={selectedNodeId}
              hiddenTypes={hiddenTypes}
              citedNodeIds={citedNodeIds}
              onNodeClick={handleNodeClick}
              onDeselect={() => setSelectedNodeId(null)}
            />
          ) : (
            <EmptyState onLoadSample={handleLoadSample} />
          )}
        </main>

        {workbenchOpen && (
          <aside
            className="w-[380px] flex flex-col border-l overflow-hidden"
            style={{ borderColor: 'var(--border)', background: 'var(--bg)' }}
          >
            <WorkbenchPanel
              graph={graph}
              contextNodeIds={contextNodeIds}
              onRemoveContext={(id) => setContextNodeIds(prev => prev.filter(x => x !== id))}
              onClearAllContext={() => setContextNodeIds([])}
              onSetContext={(ids) => setContextNodeIds([...new Set(ids)])}
              onCitationClick={(id) => { setSelectedNodeId(id); }}
              onCitedNodesChange={setCitedNodeIds}
            />
          </aside>
        )}
      </div>

      {graph && (
        <EntityLegendStrip
          entityTypes={graph.metadata.entityTypes}
          hiddenTypes={hiddenTypes}
          onToggle={handleTypeToggle}
          open={legendOpen}
          onToggleOpen={() => setLegendOpen(v => !v)}
        />
      )}
    </div>
  );
}
