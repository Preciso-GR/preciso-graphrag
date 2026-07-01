'use client';

const TYPE_PALETTE = ['#8B1A1A', '#00A896', '#1D4ED8', '#D97706', '#7C3AED', '#059669', '#DB2777', '#EA580C'];
const TYPE_NAMED: Record<string, string> = {
  ORGANIZATION: '#8B1A1A', ORG: '#8B1A1A',
  PERSON: '#00A896', PEOPLE: '#00A896',
  LOCATION: '#1D4ED8', PLACE: '#1D4ED8', GEO: '#1D4ED8',
  PRODUCT: '#D97706', BRAND: '#D97706',
  EVENT: '#7C3AED',
  CONCEPT: '#059669', CATEGORY: '#059669',
  METRIC: '#DB2777', NUMBER: '#DB2777',
  DATE: '#EA580C', TIME: '#EA580C',
};

function getTypeColor(type: string, idx: number): string {
  return TYPE_NAMED[type.toUpperCase()] ?? TYPE_PALETTE[idx % TYPE_PALETTE.length];
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
          {entries.map(([type, count], i) => {
            const hidden = hiddenTypes.has(type);
            const color = getTypeColor(type, i);
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
