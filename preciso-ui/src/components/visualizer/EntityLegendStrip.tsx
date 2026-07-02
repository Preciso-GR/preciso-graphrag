'use client';

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

interface Props {
  entityTypes: Record<string, number>;
  hiddenTypes: Set<string>;
  onToggle: (type: string) => void;
  open: boolean;
  onToggleOpen: () => void;
}

export function EntityLegendStrip({ entityTypes, hiddenTypes, onToggle, open, onToggleOpen }: Props) {
  const entries = Object.entries(entityTypes);

  return (
    <div className="shrink-0 border-t" style={{ borderColor: 'var(--border)' }}>
      {open ? (
        <div className="flex items-center gap-2 px-4 py-2 overflow-x-auto">
          <button
            onClick={onToggleOpen}
            className="shrink-0 font-mono text-xs uppercase tracking-widest hover:text-[var(--fg)] transition-colors mr-2"
            style={{ color: 'var(--muted)' }}
          >
            ▾ Legend
          </button>
          {entries.map(([type, count]) => {
            const hidden = hiddenTypes.has(type);
            const color = getTypeColor(type);
            return (
              <button
                key={type}
                onClick={() => onToggle(type)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 border font-mono text-xs transition-all whitespace-nowrap"
                style={{
                  borderColor: hidden ? 'var(--border)' : color,
                  opacity: hidden ? 0.35 : 1,
                  background: hidden ? 'transparent' : `${color}12`,
                  color: hidden ? 'var(--muted)' : 'var(--fg)',
                }}
              >
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ background: hidden ? 'var(--border)' : color }}
                />
                {type}
                <span style={{ color: 'var(--muted)', fontSize: 10 }}>({count})</span>
              </button>
            );
          })}
        </div>
      ) : (
        <button
          onClick={onToggleOpen}
          className="w-full px-4 py-1.5 font-mono text-xs text-left transition-colors"
          style={{ color: 'var(--muted)' }}
        >
          ▴ Legend ({entries.length} types)
        </button>
      )}
    </div>
  );
}
