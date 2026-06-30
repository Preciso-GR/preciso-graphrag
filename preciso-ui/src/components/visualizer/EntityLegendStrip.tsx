'use client';

interface Props {
  entityTypes: Record<string, number>;
  hiddenTypes: Set<string>;
  onToggle: (type: string) => void;
  open: boolean;
  onToggleOpen: () => void;
}

export function EntityLegendStrip({ entityTypes, hiddenTypes, onToggle, open, onToggleOpen }: Props) {
  return (
    <div
      className="shrink-0 border-t"
      style={{ borderColor: 'color-mix(in srgb, var(--muted) 20%, transparent)' }}
    >
      {open ? (
        <div className="flex items-center gap-2 px-4 py-2 overflow-x-auto">
          <button
            onClick={onToggleOpen}
            className="shrink-0 font-mono text-xs text-[var(--muted)] hover:text-[var(--fg)] transition-colors mr-1"
          >
            ▾ Legend
          </button>
          {Object.entries(entityTypes).map(([type, count]) => {
            const hidden = hiddenTypes.has(type);
            return (
              <button
                key={type}
                onClick={() => onToggle(type)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border font-mono text-xs transition-all whitespace-nowrap hover:border-[var(--fg)]"
                style={{
                  borderColor: 'color-mix(in srgb, var(--muted) 30%, transparent)',
                  opacity: hidden ? 0.4 : 1,
                  background: 'var(--bg)',
                }}
              >
                <span className="w-1.5 h-1.5 rounded-full border border-[var(--fg)]" style={{ background: 'var(--bg)' }} />
                <span style={{ color: 'var(--fg)' }}>{type}</span>
                <span style={{ color: 'var(--muted)' }}>({count})</span>
              </button>
            );
          })}
        </div>
      ) : (
        <button
          onClick={onToggleOpen}
          className="w-full px-4 py-1 font-mono text-xs text-[var(--muted)] hover:text-[var(--fg)] text-left transition-colors"
        >
          ▴ Legend
        </button>
      )}
    </div>
  );
}
