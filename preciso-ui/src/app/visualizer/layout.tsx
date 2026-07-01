import Navbar from '@/components/Navbar';
import { DesktopOnlyGuard } from '@/components/visualizer/DesktopOnlyGuard';

export const metadata = { title: 'Visualizer — Preciso' };

export default function VisualizerLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-screen flex flex-col overflow-hidden bg-[var(--bg)]">
      <Navbar />
      <div className="h-12 shrink-0" />
      <DesktopOnlyGuard>
        {children}
      </DesktopOnlyGuard>
    </div>
  );
}
