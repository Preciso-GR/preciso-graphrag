interface Planet { label: string; orbit: number; size: number; angle: number; }

const DEFAULT_PLANETS: Planet[] = [
  { label: 'MCP',         orbit: 70,  size: 8,  angle: 25 },
  { label: 'CLAUDE CODE', orbit: 100, size: 12, angle: 95 },
  { label: 'SKILLS',      orbit: 130, size: 10, angle: 170 },
  { label: 'OPENBB',      orbit: 155, size: 11, angle: 240 },
  { label: 'NEO4J',       orbit: 185, size: 10, angle: 305 },
  { label: 'QDRANT',      orbit: 210, size: 9,  angle: 355 },
];

interface Props { size?: number; planets?: Planet[]; }

export function SolarSystem({ size = 480, planets = DEFAULT_PLANETS }: Props) {
  const cx = size / 2;
  const cy = size / 2;
  const scale = size / 480;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {planets.map((p, i) => (
        <circle key={`orbit-${i}`} cx={cx} cy={cy} r={p.orbit * scale}
          fill="none" stroke="var(--fg)" strokeOpacity={0.15}
          strokeWidth={1} strokeDasharray="2 4" />
      ))}
      <g>
        <circle cx={cx} cy={cy} r={32 * scale} fill="var(--bg)" stroke="var(--fg)" strokeWidth={2} />
        <text x={cx} y={cy} textAnchor="middle" dominantBaseline="central"
          fontSize={11 * scale} fontFamily="var(--font-geist-mono, monospace)"
          fontWeight={600} fill="var(--fg)">PRECISO</text>
      </g>
      {planets.map((p) => {
        const rad = (p.angle * Math.PI) / 180;
        const px = cx + Math.cos(rad) * p.orbit * scale;
        const py = cy + Math.sin(rad) * p.orbit * scale;
        const lx = cx + Math.cos(rad) * (p.orbit + p.size + 12) * scale;
        const ly = cy + Math.sin(rad) * (p.orbit + p.size + 12) * scale;
        return (
          <g key={p.label}>
            <circle cx={px} cy={py} r={p.size * scale} fill="var(--bg)" stroke="var(--fg)" strokeWidth={1.5} />
            <text x={lx} y={ly} textAnchor="middle" dominantBaseline="central"
              fontSize={9 * scale} fontFamily="var(--font-geist-mono, monospace)"
              fill="var(--fg)" opacity={0.7}>{p.label}</text>
          </g>
        );
      })}
    </svg>
  );
}
