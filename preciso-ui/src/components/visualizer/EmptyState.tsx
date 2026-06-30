import { SolarSystem } from './SolarSystem';

interface Props { onLoadSample: () => void; }

export function EmptyState({ onLoadSample }: Props) {
  return (
    <div className="absolute inset-0 flex items-center justify-center flex-col gap-6">
      <SolarSystem size={260} />
      <div className="text-center max-w-md">
        <div className="font-mono text-xs text-[var(--muted)] uppercase tracking-widest mb-3">
          No graph loaded
        </div>
        <p className="text-sm text-[var(--fg)] mb-6 leading-relaxed">
          Drop a <span className="font-mono bg-[var(--surface)] px-1.5 py-0.5 rounded">.graphml</span> file anywhere,
          or load the Walmart sample to start exploring.
        </p>
        <button
          onClick={onLoadSample}
          className="px-4 py-2 bg-[var(--stripe)] text-[var(--stripe-text)] text-sm font-mono hover:bg-[var(--red-bright)] transition-colors"
        >
          Load Walmart sample →
        </button>
      </div>
    </div>
  );
}
