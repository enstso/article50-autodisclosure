import { activityEntries } from "../lib/presentation";

function eventTone(event: string): { dot: string; surface: string } {
  if (/failed|rejected/i.test(event)) {
    return { dot: "bg-rose-500", surface: "border-rose-100 bg-rose-50/60" };
  }
  if (/gap|no relevant|waiting|review/i.test(event)) {
    return { dot: "bg-amber-500", surface: "border-amber-100 bg-amber-50/40" };
  }
  if (/passed|successfully|approved|detected|confirmed|completed|ready/i.test(event)) {
    return { dot: "bg-emerald-500", surface: "border-emerald-100 bg-emerald-50/40" };
  }
  return { dot: "bg-indigo-500", surface: "border-slate-200 bg-white" };
}

export function AgentTimeline({ events }: { events: string[] }) {
  const entries = activityEntries(events);
  return (
    <section id="activity" className="scroll-mt-24 rounded-2xl border border-slate-200 bg-white shadow-panel">
      <div className="flex flex-col gap-3 border-b border-slate-200 px-6 py-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow">Operational audit trail</p>
          <h2 className="mt-1 text-xl font-bold tracking-tight text-slate-950">Agent Activity</h2>
        </div>
        <p className="max-w-md text-xs leading-5 text-slate-500">
          Real application actions only. Private model reasoning and hidden prompts are never shown.
        </p>
      </div>
      <ol className="px-6 py-6">
        {entries.map((entry, index) => {
          const tone = eventTone(entry.label);
          return (
            <li key={`${entry.order}-${entry.label}`} className="relative flex gap-4 pb-4 last:pb-0">
              {index < entries.length - 1 && (
                <span className="absolute left-[15px] top-8 h-full w-px bg-slate-200" aria-hidden="true" />
              )}
              <span className={`relative z-10 mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-4 border-white text-[10px] font-bold text-white ${tone.dot}`}>
                {String(entry.order).padStart(2, "0")}
              </span>
              <div className={`min-w-0 flex-1 rounded-xl border px-4 py-3 ${tone.surface}`}>
                <p className="text-sm font-semibold text-slate-800">{entry.label}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
