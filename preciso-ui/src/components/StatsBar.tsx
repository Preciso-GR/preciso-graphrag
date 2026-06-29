import RevealSection from "./RevealSection";

export default function StatsBar() {
  return (
    <section className="bg-[var(--dark-strip)] text-[#F5EDE8] py-14">
      <div className="max-w-6xl mx-auto px-6">
        <RevealSection className="flex flex-col sm:flex-row items-center justify-between gap-8">
          <p className="font-barlow text-lg uppercase tracking-widest text-[#6A4040]">
            Benchmark — Walmart FY2022 + FY2023 10-K
          </p>
          <div className="flex flex-wrap gap-10">
            {[
              { label: "GPT-4 standard RAG",   val: "~19%",  ours: false },
              { label: "GPT-4 long context",   val: "~79%",  ours: false },
              { label: "Preciso",              val: "95.4%", ours: true  },
            ].map((item) => (
              <div key={item.label} className="text-center">
                <p className={`font-barlow text-5xl leading-none ${item.ours ? "text-[var(--red-bright)]" : "text-[#3A2222]"}`}>
                  {item.val}
                </p>
                <p className="text-xs font-mono text-[#6A4040] uppercase tracking-wider mt-1">{item.label}</p>
              </div>
            ))}
          </div>
        </RevealSection>
      </div>
    </section>
  );
}
