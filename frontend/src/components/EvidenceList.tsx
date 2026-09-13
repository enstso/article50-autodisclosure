import type { Evidence } from "../types/api";

const evidenceLabels: Record<Evidence["type"], string> = {
  AI_USAGE: "AI provider detected",
  USER_INTERACTION: "Frontend interaction",
  API_ROUTE: "User-facing API route",
  BACKEND_HANDLER: "Backend handler",
  MODEL_CALL: "Model invocation",
  MODEL_CONFIGURATION: "Model configuration",
  DISCLOSURE: "Transparency disclosure",
  DISCLOSURE_ABSENCE: "Disclosure search",
  UI_CONTEXT: "Interface context",
};

export function EvidenceList({ evidence }: { evidence: Evidence[] }) {
  if (evidence.length === 0) return null;
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {evidence.map((item, index) => (
        <article key={`${item.file}-${item.line}-${item.type}-${index}`} className="min-w-0 overflow-hidden rounded-xl border border-slate-200 bg-slate-50/70">
          <div className="flex flex-col gap-1 border-b border-slate-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <span className="text-xs font-bold text-slate-800">{evidenceLabels[item.type]}</span>
            <code className="break-all text-[11px] text-indigo-700">
              {item.file}{item.line ? `:${item.line}` : ""}
            </code>
          </div>
          <pre className="whitespace-pre-wrap break-words px-4 py-3 font-mono text-[11px] leading-5 text-slate-600">
            <code>{item.snippet}</code>
          </pre>
        </article>
      ))}
    </div>
  );
}
