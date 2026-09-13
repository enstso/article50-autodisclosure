import type { AIInteractionFlow } from "../types/api";
import { EvidenceList } from "./EvidenceList";

function flowSteps(interaction: AIInteractionFlow) {
  return [
    { label: "React Chat UI", value: interaction.frontend_entrypoint },
    { label: interaction.api_endpoint || "API route", value: "User request" },
    { label: "FastAPI", value: interaction.backend_handler },
    {
      label: interaction.ai_provider || "AI model",
      value: interaction.ai_model || "Model invocation",
    },
  ].filter((step) => Boolean(step.value));
}

export function InteractionFlow({ interaction }: { interaction: AIInteractionFlow }) {
  const steps = flowSteps(interaction);
  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-panel">
      <div className="flex flex-col gap-4 border-b border-slate-200 px-6 py-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="eyebrow">AI Interaction</p>
          <h2 className="mt-1 text-xl font-bold tracking-tight text-slate-950">{interaction.name}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{interaction.flow_summary}</p>
        </div>
        <div className="shrink-0 rounded-xl bg-slate-950 px-3 py-2 text-center text-white">
          <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Confidence</p>
          <p className="mt-0.5 text-lg font-bold">{Math.round(interaction.confidence * 100)}%</p>
        </div>
      </div>

      <div className="px-6 py-6">
        <ol className="grid gap-3 lg:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr] lg:items-center">
          {steps.map((step, index) => (
            <li key={`${step.label}-${step.value}`} className="contents">
              <div className="min-w-0 rounded-xl border border-slate-200 bg-slate-50 px-4 py-4">
                <p className="text-xs font-bold text-slate-900">{step.label}</p>
                <code className="mt-2 block break-all text-[10px] leading-4 text-slate-500">{step.value}</code>
              </div>
              {index < steps.length - 1 && (
                <span className="rotate-90 text-center text-xl font-light text-indigo-400 lg:rotate-0" aria-hidden="true">→</span>
              )}
            </li>
          ))}
        </ol>
      </div>

      <div className="border-t border-slate-200 bg-slate-50/50 px-6 py-6">
        <div className="mb-4 flex items-center justify-between gap-4">
          <div>
            <p className="eyebrow">Evidence</p>
            <h3 className="mt-1 text-base font-bold text-slate-900">Why the interaction is trusted</h3>
          </div>
          <span className="text-xs text-slate-500">{interaction.evidence.length} source signals</span>
        </div>
        <EvidenceList evidence={interaction.evidence} />
      </div>
    </section>
  );
}
