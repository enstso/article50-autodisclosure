import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { createScan } from "../api/scans";
import { AppShell } from "../components/AppShell";
import {
  DEMO_REPOSITORY_URL,
  friendlyAnalysisError,
  isValidRepositoryInput,
} from "../lib/presentation";

export function HomePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const useDemo = Boolean((location.state as { useDemo?: boolean } | null)?.useDemo);
  const [repositoryUrl, setRepositoryUrl] = useState(useDemo ? DEMO_REPOSITORY_URL : "");
  const [inputError, setInputError] = useState<string | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const demoSelected = repositoryUrl === DEMO_REPOSITORY_URL;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isValidRepositoryInput(repositoryUrl)) {
      setInputError("Enter a valid public GitHub repository URL.");
      return;
    }
    setIsAnalyzing(true);
    setInputError(null);
    setRequestError(null);
    try {
      const scan = await createScan(repositoryUrl);
      navigate(`/scan/${scan.id}`, { state: { initialScan: scan } });
    } catch (error) {
      setRequestError(error instanceof Error ? error.message : "Analysis could not be started.");
    } finally {
      setIsAnalyzing(false);
    }
  }

  const requestPresentation = requestError ? friendlyAnalysisError(requestError) : null;

  return (
    <AppShell>
      <main>
        <section className="relative overflow-hidden border-b border-slate-200 bg-white">
          <div className="hero-grid absolute inset-0 opacity-60" aria-hidden="true" />
          <div className="relative mx-auto grid max-w-7xl gap-14 px-5 py-16 sm:px-8 sm:py-24 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:py-28">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-bold text-indigo-700 shadow-sm">
                <span className="h-2 w-2 rounded-full bg-indigo-500" />
                EU AI Act Article 50 Readiness
              </div>
              <h1 className="mt-7 max-w-3xl text-4xl font-black leading-[1.05] tracking-[-0.04em] text-slate-950 sm:text-6xl">
                Your AI feature should not reach users
                <span className="text-indigo-600"> without telling them it is AI.</span>
              </h1>
              <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">
                Detect missing AI transparency disclosures before release. Review a minimal fix,
                approve the change, and verify the result automatically.
              </p>
              <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-sm font-semibold text-slate-600">
                <TrustPoint>Evidence-backed findings</TrustPoint>
                <TrustPoint>Human approval required</TrustPoint>
                <TrustPoint>Repository code never runs</TrustPoint>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="relative rounded-3xl border border-slate-200 bg-white p-6 shadow-hero sm:p-8">
              <div className="absolute -right-3 -top-3 rounded-full bg-slate-950 px-3 py-1 text-[10px] font-extrabold uppercase tracking-wider text-white shadow-lg">
                Analyze before release
              </div>
              <p className="eyebrow text-indigo-700">Repository Analysis</p>
              <h2 className="mt-2 text-2xl font-bold tracking-tight text-slate-950">Find the transparency gap</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                Scan a public GitHub repository or use the controlled demo fixture.
              </p>

              <label htmlFor="repository-url" className="mt-7 block text-sm font-bold text-slate-800">Repository URL</label>
              <div className={`mt-2 flex items-center rounded-xl border bg-white px-3 transition focus-within:ring-4 ${inputError ? "border-rose-300 focus-within:border-rose-400 focus-within:ring-rose-100" : "border-slate-300 focus-within:border-indigo-500 focus-within:ring-indigo-100"}`}>
                <span className="select-none text-slate-400" aria-hidden="true">⌁</span>
                <input
                  id="repository-url"
                  name="repository-url"
                  type="text"
                  inputMode="url"
                  autoComplete="url"
                  value={demoSelected ? "Demo repository · article50-ai-chatbot" : repositoryUrl}
                  onChange={(event) => {
                    setRepositoryUrl(event.target.value);
                    setInputError(null);
                  }}
                  onFocus={() => {
                    if (demoSelected) setRepositoryUrl("");
                  }}
                  placeholder="https://github.com/example/ai-chatbot"
                  aria-invalid={Boolean(inputError)}
                  aria-describedby={inputError ? "repository-error" : "repository-help"}
                  disabled={isAnalyzing}
                  className="min-w-0 flex-1 border-0 bg-transparent px-3 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400"
                />
                {demoSelected && <span className="rounded bg-violet-100 px-2 py-1 text-[10px] font-bold text-violet-700">DEMO</span>}
              </div>
              <p id="repository-help" className="mt-2 text-xs text-slate-500">Only public GitHub repositories are accessed.</p>
              {inputError && <p id="repository-error" className="mt-2 text-xs font-semibold text-rose-700" role="alert">{inputError}</p>}

              <button type="submit" disabled={isAnalyzing} className="primary-button mt-6 w-full justify-center py-3.5">
                {isAnalyzing ? (
                  <><span className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-200 border-t-white" />Analyzing Repository…</>
                ) : (
                  <>Analyze Repository <span aria-hidden="true">→</span></>
                )}
              </button>

              <div className="my-4 flex items-center gap-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                <span className="h-px flex-1 bg-slate-200" />or<span className="h-px flex-1 bg-slate-200" />
              </div>
              <button
                type="button"
                disabled={isAnalyzing}
                onClick={() => {
                  setRepositoryUrl(DEMO_REPOSITORY_URL);
                  setInputError(null);
                  setRequestError(null);
                }}
                className="secondary-button w-full justify-center"
              >
                Try Demo Repository
              </button>
              <p className="mt-3 text-center text-[11px] leading-5 text-slate-500">
                Controlled local fixture · active model from backend configuration · real scan, patch, and verification pipeline
              </p>

              {isAnalyzing && <AnalysisProgress demo={demoSelected} />}
              {requestPresentation && (
                <div className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4" role="alert">
                  <p className="text-sm font-bold text-rose-950">{requestPresentation.title}</p>
                  <p className="mt-1 text-xs leading-5 text-rose-800">{requestPresentation.detail}</p>
                </div>
              )}
            </form>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-5 py-14 sm:px-8 sm:py-20">
          <div className="grid gap-5 md:grid-cols-3">
            <StoryCard number="01" title="Detect the interaction" description="Trace the user journey from interface to API, backend handler, and AI model." />
            <StoryCard number="02" title="Review the evidence" description="See the exact source files and lines behind every transparency readiness finding." />
            <StoryCard number="03" title="Approve and verify" description="Keep a human in control, apply a bounded patch, and re-scan the affected interaction." />
          </div>
          <div className="mt-8 flex flex-col items-center justify-between gap-5 rounded-2xl border border-slate-200 bg-slate-950 px-6 py-5 text-white sm:flex-row">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-indigo-300">Agent architecture</p>
              <p className="mt-1 text-sm text-slate-300">Built with Strands Agents SDK + Amazon Bedrock</p>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-2 text-xs font-bold">
              {["React", "FastAPI", "Strands Agent", "Amazon Bedrock"].map((item, index) => (
                <span key={item} className="contents">
                  <span className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2">{item}</span>
                  {index < 3 && <span className="text-indigo-400" aria-hidden="true">→</span>}
                </span>
              ))}
            </div>
          </div>
        </section>
      </main>
    </AppShell>
  );
}

function TrustPoint({ children }: { children: string }) {
  return <span className="flex items-center gap-2"><span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 text-[11px] font-black text-emerald-700">✓</span>{children}</span>;
}

function StoryCard({ number, title, description }: { number: string; title: string; description: string }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <span className="text-xs font-black tracking-wider text-indigo-500">{number}</span>
      <h2 className="mt-4 text-lg font-bold text-slate-950">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
    </article>
  );
}

function AnalysisProgress({ demo }: { demo: boolean }) {
  return (
    <div className="mt-5 rounded-xl border border-indigo-200 bg-indigo-50 p-4" role="status" aria-live="polite">
      <p className="text-sm font-bold text-indigo-950">{demo ? "Running controlled demo analysis" : "Repository analysis in progress"}</p>
      <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-indigo-800">
        <span>• Repository cloning</span><span>• AI usage detection</span>
        <span>• Interaction reconstruction</span><span>• Article 50 analysis</span>
      </div>
    </div>
  );
}
