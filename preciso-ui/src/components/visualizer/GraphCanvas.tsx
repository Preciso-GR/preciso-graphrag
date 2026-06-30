'use client';
import { useEffect, useRef, useCallback } from 'react';
import {
  forceSimulation, forceManyBody, forceLink,
  forceCenter, forceCollide, type SimulationNodeDatum
} from 'd3-force';
import type { GraphNode, GraphEdge, ParsedGraph } from '@/lib/graph-types';

interface Props {
  graph: ParsedGraph;
  selectedNodeId: string | null;
  hiddenTypes: Set<string>;
  citedNodeIds: string[];
  onNodeClick: (nodeId: string) => void;
  onDeselect: () => void;
}

function mulberry32(seed: number) {
  return function () {
    seed = (seed + 0x6D2B79F5) | 0;
    let t = seed;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function drawRoughCircle(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, seed: number) {
  const rng = mulberry32(seed);
  const jitter = 0.8;
  ctx.beginPath();
  const segments = 36;
  for (let i = 0; i <= segments; i++) {
    const angle = (i / segments) * Math.PI * 2;
    const jx = x + Math.cos(angle) * (r + (rng() - 0.5) * jitter);
    const jy = y + Math.sin(angle) * (r + (rng() - 0.5) * jitter);
    if (i === 0) ctx.moveTo(jx, jy);
    else ctx.lineTo(jx, jy);
  }
  ctx.closePath();
}

type SimNode = GraphNode & SimulationNodeDatum;

export function GraphCanvas({ graph, selectedNodeId, hiddenTypes, citedNodeIds, onNodeClick, onDeselect }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef({
    nodes: [] as SimNode[],
    edges: [] as GraphEdge[],
    sim: null as ReturnType<typeof forceSimulation<SimNode>> | null,
    zoom: 1,
    panX: 0,
    panY: 0,
    draggingNode: null as SimNode | null,
    isPanning: false,
    lastMouse: { x: 0, y: 0 },
    hoverNode: null as SimNode | null,
    citedTimestamps: {} as Record<string, number>,
    rafId: 0,
    selectedNodeId: null as string | null,
    hiddenTypes: new Set<string>(),
    citedNodeIds: [] as string[],
  });

  const getNodeRadius = (n: GraphNode) => Math.max(12, Math.min(28, 10 + n.degree * 1.6));

  const hitTest = useCallback((wx: number, wy: number) => {
    const s = stateRef.current;
    for (let i = s.nodes.length - 1; i >= 0; i--) {
      const n = s.nodes[i];
      if (s.hiddenTypes.has(n.type)) continue;
      const r = getNodeRadius(n);
      const dx = (n.x ?? 0) - wx;
      const dy = (n.y ?? 0) - wy;
      if (dx * dx + dy * dy <= r * r) return n;
    }
    return null;
  }, []);

  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const s = stateRef.current;
    const dpr = window.devicePixelRatio || 1;
    const W = canvas.width / dpr;
    const H = canvas.height / dpr;

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);

    // Get CSS variable values
    const style = getComputedStyle(document.documentElement);
    const fgColor = style.getPropertyValue('--fg').trim() || '#1A1212';
    const bgColor = style.getPropertyValue('--bg').trim() || '#F5F0E8';
    const mutedColor = style.getPropertyValue('--muted').trim() || '#7A6E67';
    const stripeColor = style.getPropertyValue('--stripe').trim() || '#8B1A1A';

    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, W, H);

    ctx.save();
    ctx.translate(s.panX, s.panY);
    ctx.scale(s.zoom, s.zoom);

    const selectedId = s.selectedNodeId;
    const hasSelection = selectedId !== null;

    // Get adjacency for dimming
    const adjacentIds = new Set<string>();
    if (hasSelection) {
      s.edges.forEach((e) => {
        const src = typeof e.source === 'string' ? e.source : (e.source as GraphNode).id;
        const tgt = typeof e.target === 'string' ? e.target : (e.target as GraphNode).id;
        if (src === selectedId) adjacentIds.add(tgt);
        if (tgt === selectedId) adjacentIds.add(src);
      });
    }

    // Draw edges
    s.edges.forEach((e) => {
      const src = typeof e.source === 'object' ? e.source as SimNode : s.nodes.find(n => n.id === (e.source as string));
      const tgt = typeof e.target === 'object' ? e.target as SimNode : s.nodes.find(n => n.id === (e.target as string));
      if (!src || !tgt) return;
      if (s.hiddenTypes.has(src.type) || s.hiddenTypes.has(tgt.type)) return;

      const srcId = src.id;
      const tgtId = tgt.id;
      const isConnected = !hasSelection || srcId === selectedId || tgtId === selectedId;
      const alpha = hasSelection ? (isConnected ? 0.35 : 0.08) : 0.35;
      const w = Math.max(0.5, Math.min(1.2, e.weight));

      ctx.beginPath();
      ctx.moveTo(src.x ?? 0, src.y ?? 0);
      ctx.lineTo(tgt.x ?? 0, tgt.y ?? 0);
      ctx.strokeStyle = fgColor;
      ctx.globalAlpha = alpha;
      ctx.lineWidth = w;
      ctx.stroke();

      // Edge labels when zoomed in
      if (s.zoom > 0.7 && e.label && isConnected) {
        const mx = ((src.x ?? 0) + (tgt.x ?? 0)) / 2;
        const my = ((src.y ?? 0) + (tgt.y ?? 0)) / 2;
        ctx.globalAlpha = alpha * 0.8;
        ctx.font = `9px monospace`;
        ctx.fillStyle = mutedColor;
        ctx.textAlign = 'center';
        ctx.fillText(e.label, mx, my);
      }
    });

    ctx.globalAlpha = 1;

    // Draw nodes
    const now = Date.now();
    s.nodes.forEach((n) => {
      if (s.hiddenTypes.has(n.type)) return;
      const r = getNodeRadius(n);
      const nx = n.x ?? 0;
      const ny = n.y ?? 0;
      const isSelected = n.id === selectedId;
      const isAdjacent = adjacentIds.has(n.id);
      const nodeAlpha = hasSelection ? (isSelected || isAdjacent ? 1 : 0.25) : 1;
      const isCited = s.citedNodeIds.includes(n.id);
      const citedAt = s.citedTimestamps[n.id];
      const citedAlpha = isCited && citedAt ? Math.max(0, 1 - (now - citedAt) / 4000) : 0;
      const isHovered = s.hoverNode?.id === n.id;

      ctx.globalAlpha = nodeAlpha;

      // Cited ring
      if (citedAlpha > 0) {
        ctx.beginPath();
        ctx.arc(nx, ny, r + 6, 0, Math.PI * 2);
        ctx.strokeStyle = stripeColor;
        ctx.globalAlpha = nodeAlpha * citedAlpha * 0.6;
        ctx.lineWidth = 4;
        ctx.stroke();
        ctx.globalAlpha = nodeAlpha;
      }

      // Node fill
      drawRoughCircle(ctx, nx, ny, r, n._jitterSeed ?? 0);
      ctx.fillStyle = bgColor;
      ctx.fill();

      // Node stroke
      const strokeW = isSelected ? 2.5 : isHovered ? 2 : 1.5;
      const strokeC = isSelected ? stripeColor : fgColor;
      ctx.strokeStyle = strokeC;
      ctx.lineWidth = strokeW;
      drawRoughCircle(ctx, nx, ny, r, n._jitterSeed ?? 0);
      ctx.stroke();

      // Entity type tag inside node
      ctx.font = `9px monospace`;
      ctx.fillStyle = mutedColor;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const typeLabel = n.type.length > 7 ? n.type.slice(0, 6) + '…' : n.type;
      ctx.fillText(typeLabel, nx, ny);

      // Node label below
      ctx.font = `11px monospace`;
      ctx.fillStyle = fgColor;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      const label = n.label.length > 18 ? n.label.slice(0, 17) + '…' : n.label;
      ctx.fillText(label, nx, ny + r + 4);

      ctx.globalAlpha = 1;
    });

    ctx.restore();

    // Tooltip overlay
    if (s.hoverNode) {
      const n = s.hoverNode;
      const desc = n.description ? n.description.slice(0, 80) + (n.description.length > 80 ? '…' : '') : '';
      const lines = [`${n.label} (${n.type})`, desc].filter(Boolean);
      ctx.save();
      ctx.font = '11px monospace';
      const maxW = Math.max(...lines.map(l => ctx.measureText(l).width));
      const boxW = maxW + 16;
      const boxH = lines.length * 16 + 12;
      ctx.fillStyle = bgColor;
      ctx.strokeStyle = fgColor;
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.95;
      ctx.fillRect(8, 8, boxW, boxH);
      ctx.strokeRect(8, 8, boxW, boxH);
      ctx.globalAlpha = 1;
      ctx.fillStyle = fgColor;
      ctx.textBaseline = 'top';
      ctx.textAlign = 'left';
      lines.forEach((l, i) => ctx.fillText(l, 16, 14 + i * 16));
      ctx.restore();
    }

    ctx.restore();
  }, []);

  // Init graph and simulation
  useEffect(() => {
    const s = stateRef.current;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const W = rect.width;
    const H = rect.height;
    canvas.width = W * dpr;
    canvas.height = H * dpr;

    // Clone nodes with jitter seeds
    s.nodes = graph.nodes.map((n, i) => ({ ...n, _jitterSeed: (i + 1) * 12345 })) as SimNode[];
    s.edges = graph.edges.map(e => ({ ...e }));
    s.zoom = 1;
    s.panX = 0;
    s.panY = 0;

    const sim = forceSimulation<SimNode>(s.nodes)
      .force('charge', forceManyBody().strength(-400))
      .force('link', forceLink<SimNode, GraphEdge>(s.edges).id((d) => d.id).distance(120).strength(0.5))
      .force('center', forceCenter(W / 2, H / 2))
      .force('collide', forceCollide<SimNode>().radius((d) => 14 + d.degree * 1.6 + 4))
      .alphaMin(0.005)
      .on('tick', () => {
        cancelAnimationFrame(s.rafId);
        s.rafId = requestAnimationFrame(render);
      });

    s.sim = sim;
    return () => { sim.stop(); cancelAnimationFrame(s.rafId); };
  }, [graph, render]);

  // Sync selected/hidden/cited into ref
  useEffect(() => {
    const s = stateRef.current;
    s.selectedNodeId = selectedNodeId;
    s.hiddenTypes = hiddenTypes;
    // When new cited nodes arrive, record timestamp
    citedNodeIds.forEach(id => {
      if (!s.citedTimestamps[id]) s.citedTimestamps[id] = Date.now();
    });
    s.citedNodeIds = citedNodeIds;
    // Clear timestamps for nodes no longer cited
    Object.keys(s.citedTimestamps).forEach(id => {
      if (!citedNodeIds.includes(id)) delete s.citedTimestamps[id];
    });
    render();
  }, [selectedNodeId, hiddenTypes, citedNodeIds, render]);

  // Mouse events
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const s = stateRef.current;

    const toWorld = (clientX: number, clientY: number) => {
      const rect = canvas.getBoundingClientRect();
      return {
        x: (clientX - rect.left - s.panX) / s.zoom,
        y: (clientY - rect.top - s.panY) / s.zoom,
      };
    };

    const onMouseDown = (e: MouseEvent) => {
      s.lastMouse = { x: e.clientX, y: e.clientY };
      const w = toWorld(e.clientX, e.clientY);
      const hit = hitTest(w.x, w.y);
      if (hit) {
        s.draggingNode = hit;
        hit.fx = hit.x;
        hit.fy = hit.y;
        s.sim?.alpha(0.3).restart();
      } else {
        s.isPanning = true;
      }
    };

    const onMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - s.lastMouse.x;
      const dy = e.clientY - s.lastMouse.y;
      s.lastMouse = { x: e.clientX, y: e.clientY };
      if (s.draggingNode) {
        const w = toWorld(e.clientX, e.clientY);
        s.draggingNode.fx = w.x;
        s.draggingNode.fy = w.y;
      } else if (s.isPanning) {
        s.panX += dx;
        s.panY += dy;
        cancelAnimationFrame(s.rafId);
        s.rafId = requestAnimationFrame(render);
      } else {
        const w = toWorld(e.clientX, e.clientY);
        const prev = s.hoverNode;
        s.hoverNode = hitTest(w.x, w.y);
        if (s.hoverNode !== prev) {
          canvas.style.cursor = s.hoverNode ? 'pointer' : 'default';
          cancelAnimationFrame(s.rafId);
          s.rafId = requestAnimationFrame(render);
        }
      }
    };

    const onMouseUp = () => {
      if (s.draggingNode) {
        s.draggingNode.fx = null;
        s.draggingNode.fy = null;
        s.draggingNode = null;
      }
      s.isPanning = false;
    };

    const onClick = (e: MouseEvent) => {
      const w = toWorld(e.clientX, e.clientY);
      const hit = hitTest(w.x, w.y);
      if (hit) onNodeClick(hit.id);
      else onDeselect();
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      const newZoom = Math.max(0.2, Math.min(4, s.zoom * factor));
      s.panX = mx - (mx - s.panX) * (newZoom / s.zoom);
      s.panY = my - (my - s.panY) * (newZoom / s.zoom);
      s.zoom = newZoom;
      cancelAnimationFrame(s.rafId);
      s.rafId = requestAnimationFrame(render);
    };

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onDeselect();
    };

    canvas.addEventListener('mousedown', onMouseDown);
    canvas.addEventListener('mousemove', onMouseMove);
    canvas.addEventListener('mouseup', onMouseUp);
    canvas.addEventListener('click', onClick);
    canvas.addEventListener('wheel', onWheel, { passive: false });
    window.addEventListener('keydown', onKeyDown);

    const ro = new ResizeObserver(() => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      render();
    });
    ro.observe(canvas);

    return () => {
      canvas.removeEventListener('mousedown', onMouseDown);
      canvas.removeEventListener('mousemove', onMouseMove);
      canvas.removeEventListener('mouseup', onMouseUp);
      canvas.removeEventListener('click', onClick);
      canvas.removeEventListener('wheel', onWheel);
      window.removeEventListener('keydown', onKeyDown);
      ro.disconnect();
    };
  }, [hitTest, onNodeClick, onDeselect, render]);

  return <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />;
}
