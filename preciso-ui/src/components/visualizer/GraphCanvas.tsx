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

// Precise pencil wobble — engineer's sketch, not napkin scrawl
function drawRoughCircle(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, seed: number) {
  const rng = mulberry32(seed);
  const jitter = 0.3; // absolute px — subtle, deliberate
  const segments = 48;
  ctx.beginPath();
  for (let i = 0; i <= segments; i++) {
    const angle = (i / segments) * Math.PI * 2;
    const jr = r + (rng() - 0.5) * jitter * 2;
    const jx = x + Math.cos(angle) * jr;
    const jy = y + Math.sin(angle) * jr;
    if (i === 0) ctx.moveTo(jx, jy);
    else ctx.lineTo(jx, jy);
  }
  ctx.closePath();
}

// ── Color palette (synced with EntityLegendStrip) ────────────────────────────
const TYPE_PALETTE = ['#00C2A8', '#F59E0B', '#60A5FA', '#A78BFA', '#4ADE80', '#FB923C', '#F472B6', '#34D399'];
const TYPE_NAMED: Record<string, string> = {
  COMPANY: '#00C2A8', CORPORATION: '#00C2A8', ORG: '#00C2A8', ORGANIZATION: '#00C2A8',
  PERSON: '#F59E0B', PEOPLE: '#F59E0B', INDIVIDUAL: '#F59E0B', EXECUTIVE: '#F59E0B',
  FINANCIAL: '#60A5FA', FINANCE: '#60A5FA', METRIC: '#60A5FA', NUMBER: '#60A5FA',
  SEGMENT: '#A78BFA', DIVISION: '#A78BFA', UNIT: '#A78BFA',
  GEO: '#4ADE80', GEOGRAPHY: '#4ADE80', LOCATION: '#4ADE80', REGION: '#4ADE80', PLACE: '#4ADE80', COUNTRY: '#4ADE80',
  RISK: '#FB923C', CHALLENGE: '#FB923C',
  EVENT: '#F472B6', DATE: '#F472B6',
  PRODUCT: '#34D399', BRAND: '#34D399', CONCEPT: '#34D399', CATEGORY: '#34D399',
};

function typeHash(type: string): number {
  let h = 0;
  for (let i = 0; i < type.length; i++) h = (h * 31 + type.charCodeAt(i)) | 0;
  return Math.abs(h);
}

function getTypeColor(type: string): string {
  return TYPE_NAMED[type.toUpperCase()] ?? TYPE_PALETTE[typeHash(type) % TYPE_PALETTE.length];
}

function hexAlpha(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
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

  const getNodeRadius = (n: GraphNode) => Math.max(20, Math.min(44, 16 + n.degree * 3));

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

    const style = getComputedStyle(document.documentElement);
    const fgColor   = style.getPropertyValue('--fg').trim()     || '#1A1212';
    const bgColor   = style.getPropertyValue('--bg').trim()     || '#F5F0E8';
    const mutedColor= style.getPropertyValue('--muted').trim()  || '#7A6E67';
    const stripeColor= style.getPropertyValue('--stripe').trim()|| '#8B1A1A';

    // Background fill
    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, W, H);

    // Dot grid — screen-space, fixed (workbench paper texture)
    const gridSpacing = 28;
    ctx.fillStyle = mutedColor;
    ctx.globalAlpha = 0.16;
    for (let gx = gridSpacing / 2; gx < W; gx += gridSpacing) {
      for (let gy = gridSpacing / 2; gy < H; gy += gridSpacing) {
        ctx.beginPath();
        ctx.arc(gx, gy, 0.85, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.globalAlpha = 1;

    ctx.save();
    ctx.translate(s.panX, s.panY);
    ctx.scale(s.zoom, s.zoom);

    const selectedId = s.selectedNodeId;
    const hasSelection = selectedId !== null;

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

      const isConnected = !hasSelection || src.id === selectedId || tgt.id === selectedId;
      const alpha = hasSelection ? (isConnected ? 0.45 : 0.06) : 0.3;
      const w = Math.max(0.8, Math.min(1.6, e.weight));

      ctx.beginPath();
      ctx.moveTo(src.x ?? 0, src.y ?? 0);
      ctx.lineTo(tgt.x ?? 0, tgt.y ?? 0);
      ctx.strokeStyle = fgColor;
      ctx.globalAlpha = alpha;
      ctx.lineWidth = w;
      ctx.stroke();

      if (s.zoom > 0.85 && e.label && isConnected) {
        const mx = ((src.x ?? 0) + (tgt.x ?? 0)) / 2;
        const my = ((src.y ?? 0) + (tgt.y ?? 0)) / 2;
        ctx.globalAlpha = alpha * 0.65;
        ctx.font = `9px monospace`;
        ctx.fillStyle = mutedColor;
        ctx.textAlign = 'center';
        ctx.fillText(e.label, mx, my - 3);
      }
    });

    ctx.globalAlpha = 1;

    // Draw nodes — type-colored
    const now = Date.now();
    s.nodes.forEach((n) => {
      if (s.hiddenTypes.has(n.type)) return;
      const r = getNodeRadius(n);
      const nx = n.x ?? 0;
      const ny = n.y ?? 0;
      const isSelected = n.id === selectedId;
      const isAdjacent = adjacentIds.has(n.id);
      const nodeAlpha = hasSelection ? (isSelected || isAdjacent ? 1 : 0.18) : 1;
      const isHovered = s.hoverNode?.id === n.id;
      const typeColor = getTypeColor(n.type);

      const isCited = s.citedNodeIds.includes(n.id);
      const citedAt = s.citedTimestamps[n.id];
      const citedFade = isCited && citedAt ? Math.max(0, 1 - (now - citedAt) / 4000) : 0;

      ctx.globalAlpha = nodeAlpha;

      // Cited ring — dashed type-color ring
      if (citedFade > 0) {
        ctx.save();
        ctx.beginPath();
        ctx.arc(nx, ny, r + 7, 0, Math.PI * 2);
        ctx.strokeStyle = typeColor;
        ctx.globalAlpha = nodeAlpha * citedFade * 0.6;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.restore();
        ctx.globalAlpha = nodeAlpha;
      }

      // Selected outer glow ring
      if (isSelected) {
        ctx.save();
        ctx.beginPath();
        ctx.arc(nx, ny, r + 6, 0, Math.PI * 2);
        ctx.strokeStyle = stripeColor;
        ctx.globalAlpha = nodeAlpha * 0.25;
        ctx.lineWidth = 4;
        ctx.stroke();
        ctx.restore();
        ctx.globalAlpha = nodeAlpha;
      }

      // Node fill — type color tint
      drawRoughCircle(ctx, nx, ny, r, n._jitterSeed ?? 0);
      ctx.fillStyle = isSelected
        ? hexAlpha(stripeColor, 0.18)
        : hexAlpha(typeColor, 0.14);
      ctx.fill();

      // Node stroke — type color normally, stripe red when selected
      drawRoughCircle(ctx, nx, ny, r, n._jitterSeed ?? 0);
      ctx.strokeStyle = isSelected ? stripeColor : typeColor;
      ctx.lineWidth = isSelected ? 2.5 : isHovered ? 2.2 : 1.8;
      ctx.stroke();

      // Type initial — type color, prominent
      const initial = (n.type[0] ?? '?').toUpperCase();
      const fontSize = Math.max(11, Math.round(r * 0.45));
      ctx.font = `600 ${fontSize}px monospace`;
      ctx.fillStyle = isSelected ? stripeColor : typeColor;
      ctx.globalAlpha = nodeAlpha * (isSelected ? 0.9 : 0.7);
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(initial, nx, ny);
      ctx.globalAlpha = nodeAlpha;

      // Label below — bg strip for legibility
      const label = n.label.length > 16 ? n.label.slice(0, 15) + '…' : n.label;
      ctx.font = `11px monospace`;
      const lw = ctx.measureText(label).width;
      const lx = nx - lw / 2 - 3;
      const ly = ny + r + 4;

      ctx.fillStyle = bgColor;
      ctx.globalAlpha = nodeAlpha * 0.82;
      ctx.fillRect(lx, ly, lw + 6, 13);
      ctx.globalAlpha = nodeAlpha;

      ctx.fillStyle = isSelected ? stripeColor : fgColor;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillText(label, nx, ly + 1);

      ctx.globalAlpha = 1;
    });

    ctx.restore();

    // Hover tooltip
    if (s.hoverNode) {
      const n = s.hoverNode;
      const lines = [
        n.label,
        `${n.type}  ·  degree ${n.degree}`,
        ...(n.description ? [n.description.slice(0, 72) + (n.description.length > 72 ? '…' : '')] : []),
      ];
      ctx.save();
      ctx.font = '11px monospace';
      const maxW = Math.max(...lines.map(l => ctx.measureText(l).width));
      const boxW = maxW + 20;
      const boxH = lines.length * 16 + 14;

      ctx.fillStyle = bgColor;
      ctx.globalAlpha = 0.96;
      ctx.fillRect(10, 10, boxW, boxH);
      ctx.strokeStyle = fgColor;
      ctx.lineWidth = 1;
      ctx.globalAlpha = 1;
      ctx.strokeRect(10, 10, boxW, boxH);

      ctx.fillStyle = fgColor;
      ctx.textBaseline = 'top';
      ctx.textAlign = 'left';
      lines.forEach((l, i) => {
        ctx.globalAlpha = i === 0 ? 1 : 0.55;
        ctx.fillText(l, 20, 17 + i * 16);
      });
      ctx.globalAlpha = 1;
      ctx.restore();
    }

    // Zoom indicator
    ctx.save();
    ctx.font = '10px monospace';
    ctx.fillStyle = mutedColor;
    ctx.globalAlpha = 0.45;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'bottom';
    ctx.fillText(`${Math.round(s.zoom * 100)}%`, W - 8, H - 6);
    ctx.restore();

    ctx.restore();
  }, []);

  // Init simulation
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

    s.nodes = graph.nodes.map((n, i) => ({ ...n, _jitterSeed: (i + 1) * 12345 })) as SimNode[];
    s.edges = graph.edges.map(e => ({ ...e }));
    s.zoom = 1;
    s.panX = 0;
    s.panY = 0;

    const nodeR = (d: SimNode) => Math.max(20, Math.min(44, 16 + d.degree * 3));

    const sim = forceSimulation<SimNode>(s.nodes)
      .force('charge', forceManyBody().strength(-700))
      .force('link', forceLink<SimNode, GraphEdge>(s.edges).id((d) => d.id).distance(180).strength(0.4))
      .force('center', forceCenter(W / 2, H / 2))
      .force('collide', forceCollide<SimNode>().radius((d) => nodeR(d) + 10))
      .alphaMin(0.005)
      .on('tick', () => {
        cancelAnimationFrame(s.rafId);
        s.rafId = requestAnimationFrame(render);
      });

    s.sim = sim;
    return () => { sim.stop(); cancelAnimationFrame(s.rafId); };
  }, [graph, render]);

  // Sync reactive props
  useEffect(() => {
    const s = stateRef.current;
    s.selectedNodeId = selectedNodeId;
    s.hiddenTypes = hiddenTypes;
    citedNodeIds.forEach(id => {
      if (!s.citedTimestamps[id]) s.citedTimestamps[id] = Date.now();
    });
    s.citedNodeIds = citedNodeIds;
    Object.keys(s.citedTimestamps).forEach(id => {
      if (!citedNodeIds.includes(id)) delete s.citedTimestamps[id];
    });
    render();
  }, [selectedNodeId, hiddenTypes, citedNodeIds, render]);

  // Events
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
      const newZoom = Math.max(0.15, Math.min(5, s.zoom * factor));
      s.panX = mx - (mx - s.panX) * (newZoom / s.zoom);
      s.panY = my - (my - s.panY) * (newZoom / s.zoom);
      s.zoom = newZoom;
      cancelAnimationFrame(s.rafId);
      s.rafId = requestAnimationFrame(render);
    };

    const onKeyDown = (e: KeyboardEvent) => { if (e.key === 'Escape') onDeselect(); };

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
