import { FormEvent, useEffect, useState } from "react";

import { getHealth } from "../api/health";
import { createScan } from "../api/scans";
import { ApiConnectionStatus } from "../components/ApiConnectionStatus";
import type { AIInteractionFlow, ApiStatus, Evidence, Scan } from "../types/api";

export function HomePage() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [scan, setScan] = useState<Scan | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    getHealth(controller.signal)
      .then((health) => setApiStatus(health.status === "ok" ? "connected" : "offline"))
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          setApiStatus("offline");
        }
      });

    return () => controller.abort();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsAnalyzing(true);
    setRequestError(null);
    setScan(null);

    try {
      setScan(await createScan(repositoryUrl));
    } catch (error) {
      setRequestError(error instanceof Error ? error.message : "Repository analysis failed.");
    } finally {
      setIsAnalyzing(false);
    }
  }

  return (
    <div className="min-h-screen bg-canvas">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-ink text-sm font-bold text-white">
              A50
            </div>
            <span className="text-sm font-semibold tracking-tight text-ink">
              Article 50 AutoDisclosure
            </span>
          </div>
          <ApiConnectionStatus status={apiStatus} />
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-24 sm:py-32">
        <div className="mb-8 inline-flex rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600">
          EU AI Act transparency checks
        </div>
        <h1 className="max-w-2xl text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
          Article 50 AutoDisclosure
        </h1>
        <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-600">
          Analyze AI applications for missing transparency disclosures before release.
        </p>

        <form
          className="mt-12 rounded-xl border border-slate-200 bg-white p-6 shadow-panel sm:p-8"
          onSubmit={handleSubmit}
        >
          <label htmlFor="repository-url" className="block text-sm font-medium text-slate-800">
            GitHub repository URL
          </label>
          <p className="mt-1 text-sm text-slate-500">
            Enter a public repository containing an AI-powered application.
          </p>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row">
            <input
              id="repository-url"
              name="repository-url"
              type="url"
              value={repositoryUrl}
              onChange={(event) => setRepositoryUrl(event.target.value)}
              placeholder="https://github.com/organization/repository"
              required
              disabled={isAnalyzing}
              className="min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
            />
            <button
              type="submit"
              disabled={isAnalyzing}
              className="rounded-md bg-ink px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {isAnalyzing ? "Analyzing…" : "Analyze Repository"}
            </button>
          </div>
          {isAnalyzing && (
            <p className="mt-4 text-sm text-slate-600" role="status">
              Cloning and investigating the repository with the Strands agent…
            </p>
          )}
        </form>

        {requestError && (
          <div className="mt-6 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800" role="alert">
            {requestError}
          </div>
        )}

        {scan?.status === "FAILED" && (
          <div className="mt-6 rounded-lg border border-rose-200 bg-rose-50 p-4" role="alert">
            <p className="text-sm font-semibold text-rose-900">Repository analysis failed</p>
            <p className="mt-1 text-sm text-rose-800">{scan.error}</p>
          </div>
        )}

        {scan?.status === "COMPLETED" && scan.summary && (
          <section className="mt-8 rounded-xl border border-slate-200 bg-white p-6 shadow-panel sm:p-8">
            <div className="flex flex-col gap-2 border-b border-slate-200 pb-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-emerald-700">
                  Repository analyzed
                </p>
                <p className="mt-1 break-all text-sm text-slate-500">{scan.repository_url}</p>
              </div>
              <span className="w-fit rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                Completed
              </span>
            </div>

            <div className="grid gap-8 py-7 sm:grid-cols-2">
              <ResultList title="Languages" values={scan.summary.languages} />
              <ResultList title="Frameworks" values={scan.summary.frameworks} />
            </div>

            <div className="border-t border-slate-200 py-7">
              <h2 className="text-sm font-semibold text-slate-900">Architecture</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {scan.summary.architecture_summary}
              </p>
            </div>

            <div className="border-t border-slate-200 py-7">
              <ResultList title="Important files" values={scan.summary.important_files} code />
            </div>

            {scan.summary.potential_ai_integrations.length > 0 && (
              <div className="border-t border-slate-200 py-7">
                <ResultList
                  title="Potential AI integrations"
                  values={scan.summary.potential_ai_integrations}
                />
              </div>
            )}

            <AIInteractions scan={scan} />

            <div className="border-t border-slate-200 pt-7">
              <h2 className="text-sm font-semibold text-slate-900">Agent activity</h2>
              <ol className="mt-3 space-y-2">
                {scan.events.map((event, index) => (
                  <li key={`${index}-${event}`} className="flex gap-3 text-sm text-slate-600">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
                    {event}
                  </li>
                ))}
              </ol>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

function AIInteractions({ scan }: { scan: Scan }) {
  const confirmed = scan.ai_interactions.filter((interaction) => interaction.user_facing);

  return (
    <div className="border-t border-slate-200 py-7">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-sm font-semibold text-slate-900">AI Interactions</h2>
        {confirmed.length > 0 && (
          <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800">
            {confirmed.length} detected
          </span>
        )}
      </div>

      {confirmed.length === 0 ? (
        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm font-medium text-slate-800">
            No user-facing AI interaction detected.
          </p>
          {scan.ai_usages.length > 0 && (
            <p className="mt-1 text-sm text-slate-500">
              AI usage was found, but a complete user-facing path could not be confirmed.
            </p>
          )}
        </div>
      ) : (
        <div className="mt-5 space-y-6">
          {confirmed.map((interaction) => (
            <AIInteractionCard key={interaction.id} interaction={interaction} />
          ))}
        </div>
      )}
    </div>
  );
}

function AIInteractionCard({ interaction }: { interaction: AIInteractionFlow }) {
  const flow = [
    { label: "Frontend", value: interaction.frontend_entrypoint },
    { label: "API", value: interaction.api_endpoint },
    { label: "Backend", value: interaction.backend_handler },
    {
      label: "Model",
      value: [interaction.ai_provider, interaction.ai_model].filter(Boolean).join(" · "),
    },
  ].filter((step): step is { label: string; value: string } => Boolean(step.value));

  return (
    <article className="rounded-lg border border-amber-200 bg-amber-50/40 p-5 sm:p-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-amber-800">
            AI interaction detected
          </p>
          <h3 className="mt-1 text-lg font-semibold text-slate-900">{interaction.name}</h3>
        </div>
        <div className="text-left sm:text-right">
          <p className="text-xs text-slate-500">Confidence</p>
          <p className="text-lg font-semibold text-slate-900">
            {Math.round(interaction.confidence * 100)}%
          </p>
        </div>
      </div>

      <p className="mt-3 text-sm leading-6 text-slate-600">{interaction.flow_summary}</p>

      <div className="mt-6">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Flow</h4>
        <ol className="mt-3 space-y-0">
          {flow.map((step, index) => (
            <li key={`${step.label}-${step.value}`}>
              <div className="rounded-md border border-slate-200 bg-white px-4 py-3">
                <span className="text-xs font-medium text-slate-500">{step.label}</span>
                <code className="mt-1 block break-all text-xs text-slate-800">{step.value}</code>
              </div>
              {index < flow.length - 1 && (
                <div className="flex h-6 items-center pl-5 text-slate-400" aria-hidden="true">
                  ↓
                </div>
              )}
            </li>
          ))}
        </ol>
      </div>

      <div className="mt-7">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Evidence
        </h4>
        <div className="mt-3 space-y-3">
          {interaction.evidence.map((evidence, index) => (
            <EvidenceItem key={`${evidence.file}-${evidence.line}-${evidence.type}-${index}`} evidence={evidence} />
          ))}
        </div>
      </div>
    </article>
  );
}

function EvidenceItem({ evidence }: { evidence: Evidence }) {
  return (
    <div className="overflow-hidden rounded-md border border-slate-200 bg-white">
      <div className="flex flex-col gap-1 border-b border-slate-200 px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
        <code className="break-all text-xs font-medium text-slate-700">
          {evidence.file}
          {evidence.line ? `:${evidence.line}` : ""}
        </code>
        <span className="w-fit rounded bg-slate-100 px-2 py-0.5 text-[10px] font-semibold tracking-wide text-slate-600">
          {evidence.type.replace(/_/g, " ")}
        </span>
      </div>
      <pre className="overflow-x-auto whitespace-pre-wrap break-words px-3 py-3 text-xs leading-5 text-slate-700">
        <code>{evidence.snippet}</code>
      </pre>
    </div>
  );
}

interface ResultListProps {
  title: string;
  values: string[];
  code?: boolean;
}

function ResultList({ title, values, code = false }: ResultListProps) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      {values.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">None detected</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {values.map((value) => (
            <li key={value} className="flex gap-2 text-sm text-slate-600">
              <span className="text-slate-400">—</span>
              {code ? <code className="break-all text-xs text-slate-700">{value}</code> : value}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
