"use client";

import { useEffect, useRef } from "react";

interface GNode {
  id: string;
  label: string;
  type: string;
  baseX: number;
  baseY: number;
  phase: number;
  color: string;
  r: number;
}

interface GEdge {
  from: string;
  to: string;
  label: string;
}

const NODES: GNode[] = [
  { id: "apple",    label: "Apple Inc.",     type: "COMPANY",     baseX: 0.52, baseY: 0.28, phase: 0,   color: "#C8102E", r: 9 },
  { id: "tim",      label: "Tim Cook",       type: "PERSON",      baseX: 0.78, baseY: 0.44, phase: 1.5, color: "#00C2A8", r: 7 },
  { id: "supply",   label: "Supply Chain",   type: "RISK_FACTOR", baseX: 0.30, baseY: 0.42, phase: 0.8, color: "#F59E0B", r: 7 },
  { id: "services", label: "Services",       type: "SEGMENT",     baseX: 0.60, baseY: 0.70, phase: 2.1, color: "#8B5CF6", r: 6 },
  { id: "revenue",  label: "$394.3B",        type: "METRIC",      baseX: 0.20, baseY: 0.28, phase: 1.2, color: "#3B82F6", r: 6 },
  { id: "china",    label: "China Ops",      type: "REGION",      baseX: 0.80, baseY: 0.20, phase: 0.4, color: "#EC4899", r: 6 },
  { id: "walmart",  label: "Walmart",        type: "COMPANY",     baseX: 0.18, baseY: 0.66, phase: 1.8, color: "#C8102E", r: 8 },
  { id: "doug",     label: "D. McMillon",    type: "PERSON",      baseX: 0.38, baseY: 0.78, phase: 0.6, color: "#00C2A8", r: 6 },
];

const EDGES: GEdge[] = [
  { from: "apple",    to: "tim",      label: "EMPLOYS" },
  { from: "apple",    to: "supply",   label: "EXPOSED_TO" },
  { from: "apple",    to: "services", label: "OPERATES" },
  { from: "apple",    to: "revenue",  label: "REPORTED" },
  { from: "apple",    to: "china",    label: "OPERATES_IN" },
  { from: "tim",      to: "supply",   label: "MANAGES" },
  { from: "walmart",  to: "doug",     label: "EMPLOYS" },
  { from: "walmart",  to: "revenue",  label: "REPORTED" },
  { from: "services", to: "revenue",  label: "CONTRIBUTES_TO" },
];

const PATHS = [
  ["supply", "apple", "tim"],
  ["apple", "services", "revenue"],
  ["apple", "china"],
  ["walmart", "doug"],
  ["tim", "supply", "apple", "revenue"],
  ["walmart", "revenue", "services"],
];

export default function GraphAnimation() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const parent = canvas.parentElement;
    let w = parent?.clientWidth ?? 500;
    let h = parent?.clientHeight ?? 500;

    const resize = () => {
      w = parent?.clientWidth ?? 500;
      h = parent?.clientHeight ?? 500;
      canvas.width = w * devicePixelRatio;
      canvas.height = h * devicePixelRatio;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.scale(devicePixelRatio, devicePixelRatio);
    };
    resize();

    const ro = new ResizeObserver(resize);
    if (parent) ro.observe(parent);

    const getNode = (id: string) => NODES.find((n) => n.id === id)!;

    const nodePos = (node: GNode, t: number) => {
      const drift = 10;
      return {
        x: node.baseX * w + Math.sin(t * 0.0007 + node.phase) * drift,
        y: node.baseY * h + Math.cos(t * 0.0005 + node.phase * 1.4) * drift,
      };
    };

    // Traversal state
    let path: string[] = PATHS[0];
    let edgeIdx = 0;
    let trav = 0;
    let lastSwitch = 0;
    const INTERVAL = 3200;
    const SPEED = 0.007;

    const draw = (ts: number) => {
      ctx.clearRect(0, 0, w, h);

      // Cycle traversal path
      if (ts - lastSwitch > INTERVAL || path.length === 0) {
        path = PATHS[Math.floor(Math.random() * PATHS.length)];
        edgeIdx = 0;
        trav = 0;
        lastSwitch = ts;
      }

      const activeNodeIds = new Set(path.slice(0, edgeIdx + 1));
      const fromId = path[edgeIdx];
      const toId = path[edgeIdx + 1];

      // Draw edges
      for (const edge of EDGES) {
        const fn = getNode(edge.from);
        const tn = getNode(edge.to);
        if (!fn || !tn) continue;
        const fp = nodePos(fn, ts);
        const tp = nodePos(tn, ts);

        const mx = (fp.x + tp.x) / 2 + (tp.y - fp.y) * 0.18;
        const my = (fp.y + tp.y) / 2 - (tp.x - fp.x) * 0.18;

        const isActive =
          (edge.from === fromId && edge.to === toId) ||
          (edge.from === toId && edge.to === fromId);
        const isTraversed =
          activeNodeIds.has(edge.from) && activeNodeIds.has(edge.to);

        ctx.beginPath();
        ctx.moveTo(fp.x, fp.y);
        ctx.quadraticCurveTo(mx, my, tp.x, tp.y);
        ctx.strokeStyle = isActive
          ? "rgba(200,16,46,0.7)"
          : isTraversed
          ? "rgba(200,16,46,0.25)"
          : "rgba(255,255,255,0.07)";
        ctx.lineWidth = isActive ? 2 : 1;
        ctx.stroke();

        // Edge label
        const lx = (fp.x + mx + tp.x) / 3;
        const ly = (fp.y + my + tp.y) / 3;
        ctx.font = "8px var(--font-geist-mono, monospace)";
        ctx.textAlign = "center";
        ctx.fillStyle = isActive
          ? "rgba(200,16,46,0.95)"
          : "rgba(161,161,170,0.3)";
        ctx.fillText(edge.label, lx, ly);
      }

      // Traversal dot
      if (toId) {
        const fn = getNode(fromId);
        const tn = getNode(toId);
        if (fn && tn) {
          trav += SPEED;
          if (trav >= 1) {
            trav = 0;
            edgeIdx = Math.min(edgeIdx + 1, path.length - 2);
          }
          const fp = nodePos(fn, ts);
          const tp = nodePos(tn, ts);
          const mx = (fp.x + tp.x) / 2 + (tp.y - fp.y) * 0.18;
          const my = (fp.y + tp.y) / 2 - (tp.x - fp.x) * 0.18;
          const t2 = trav;
          const dx = (1-t2)*(1-t2)*fp.x + 2*(1-t2)*t2*mx + t2*t2*tp.x;
          const dy = (1-t2)*(1-t2)*fp.y + 2*(1-t2)*t2*my + t2*t2*tp.y;

          // Glow
          const grd = ctx.createRadialGradient(dx, dy, 0, dx, dy, 14);
          grd.addColorStop(0, "rgba(200,16,46,0.8)");
          grd.addColorStop(1, "rgba(200,16,46,0)");
          ctx.beginPath();
          ctx.arc(dx, dy, 14, 0, Math.PI * 2);
          ctx.fillStyle = grd;
          ctx.fill();

          ctx.beginPath();
          ctx.arc(dx, dy, 4, 0, Math.PI * 2);
          ctx.fillStyle = "#fff";
          ctx.fill();
        }
      }

      // Draw nodes
      for (const node of NODES) {
        const p = nodePos(node, ts);
        const isActive = activeNodeIds.has(node.id) || node.id === toId;

        // Glow ring
        if (isActive) {
          const grd = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, node.r * 4.5);
          grd.addColorStop(0, node.color + "30");
          grd.addColorStop(1, "transparent");
          ctx.beginPath();
          ctx.arc(p.x, p.y, node.r * 4.5, 0, Math.PI * 2);
          ctx.fillStyle = grd;
          ctx.fill();
        }

        // Node fill
        ctx.beginPath();
        ctx.arc(p.x, p.y, node.r, 0, Math.PI * 2);
        ctx.fillStyle = isActive ? node.color : node.color + "55";
        ctx.fill();
        ctx.strokeStyle = isActive ? node.color + "cc" : node.color + "30";
        ctx.lineWidth = isActive ? 2 : 1;
        ctx.stroke();

        // Label
        ctx.font = `${isActive ? "600 " : ""}11px var(--font-geist-sans, sans-serif)`;
        ctx.fillStyle = isActive ? "#FFFFFF" : "rgba(255,255,255,0.5)";
        ctx.textAlign = "center";
        ctx.fillText(node.label, p.x, p.y + node.r + 14);

        // Type badge
        ctx.font = "8px var(--font-geist-mono, monospace)";
        ctx.fillStyle = isActive ? node.color + "ee" : node.color + "55";
        ctx.fillText(node.type, p.x, p.y + node.r + 25);
      }

      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full"
      style={{ background: "transparent" }}
    />
  );
}
