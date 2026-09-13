import { scanReadiness } from "../lib/presentation";
import type { Scan } from "../types/api";
import { StatusBadge } from "./StatusBadge";

const copy = {
  PASS: {
    eyebrow: "Transparency disclosure verified",
    title: "A clear AI disclosure is visible in the relevant interface.",
    description:
      "Static verification found explicit AI wording in the user-facing interaction.",
    icon: "✓",
    surface: "border-emerald-200 bg-emerald-50/70",
    iconClass: "bg-emerald-600 text-white",
  },
  ACTION_REQUIRED: {
    eyebrow: "Transparency gap detected",
    title: "A user-facing AI interaction has no clear disclosure.",
    description:
      "Add an explicit AI transparency notice before this feature reaches users.",
    icon: "!",
    surface: "border-amber-300 bg-amber-50/80",
    iconClass: "bg-amber-500 text-white",
  },
  NEEDS_REVIEW: {
    eyebrow: "Transparency context is ambiguous",
    title: "This AI interaction needs a human review.",
    description:
      "The system detected a user-facing AI interaction, but could not confirm its disclosure context.",
    icon: "?",
    surface: "border-sky-200 bg-sky-50/70",
    iconClass: "bg-sky-600 text-white",
  },
} as const;

export function ReadinessCard({ scan }: { scan: Scan }) {
  const status = scanReadiness(scan);
  if (!status) {
    return (
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-panel">
        <p className="eyebrow">Article 50 Readiness</p>
        <h2 className="mt-2 text-2xl font-bold tracking-tight">No direct AI interaction detected</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          No Article 50 interaction disclosure finding was generated. This is a readiness result,
          not a legal certification.
        </p>
      </section>
    );
  }
  const presentation = copy[status];
  return (
    <section className={`overflow-hidden rounded-2xl border p-6 shadow-panel sm:p-8 ${presentation.surface}`}>
      <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 gap-4">
          <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-xl font-black shadow-sm ${presentation.iconClass}`} aria-hidden="true">
            {presentation.icon}
          </span>
          <div>
            <p className="eyebrow">Article 50 Readiness</p>
            <p className="mt-2 text-xs font-extrabold uppercase tracking-[0.14em] text-slate-600">
              {presentation.eyebrow}
            </p>
            <h2 className="mt-2 max-w-3xl text-2xl font-bold leading-tight tracking-tight text-slate-950 sm:text-3xl">
              {presentation.title}
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
              {presentation.description}
            </p>
          </div>
        </div>
        <StatusBadge status={status} />
      </div>
    </section>
  );
}
