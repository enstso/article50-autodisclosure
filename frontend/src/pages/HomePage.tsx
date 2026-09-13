import { FormEvent, useEffect, useState } from "react";

import { getHealth } from "../api/health";
import { approvePatch, generatePatch, rejectPatch } from "../api/patches";
import { createScan, getScan } from "../api/scans";
import { ApiConnectionStatus } from "../components/ApiConnectionStatus";
import type {
  AIInteractionFlow,
  ApiStatus,
  Evidence,
  Finding,
  PatchProposal,
  ReadinessStatus,
  Scan,
  TransparencyAssessment,
} from "../types/api";

const RESULT_STATUSES = new Set(["COMPLETED", "ACTION_REQUIRED", "PASS"]);

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

        {scan && RESULT_STATUSES.has(scan.status) && scan.summary && (
          <section className="mt-8 rounded-xl border border-slate-200 bg-white p-6 shadow-panel sm:p-8">
            <div className="flex flex-col gap-2 border-b border-slate-200 pb-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-emerald-700">
                  Repository analyzed
                </p>
                <p className="mt-1 break-all text-sm text-slate-500">{scan.repository_url}</p>
              </div>
              <span className="w-fit rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                {scan.status === "PASS"
                  ? "Ready"
                  : scan.status === "ACTION_REQUIRED"
                    ? "Action required"
                    : "Completed"}
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

            <Article50Readiness scan={scan} onScanChange={setScan} />

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

function Article50Readiness({
  scan,
  onScanChange,
}: {
  scan: Scan;
  onScanChange: (scan: Scan) => void;
}) {
  const [proposals, setProposals] = useState<Record<string, PatchProposal>>({});
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [patchError, setPatchError] = useState<string | null>(null);
  const assessments = scan.article50_assessments;
  const status: ReadinessStatus | null = scan.status === "PASS"
    ? "PASS"
    : scan.status === "ACTION_REQUIRED"
      ? "ACTION_REQUIRED"
      : assessments.some((assessment) => assessment.status === "NEEDS_REVIEW")
        ? "NEEDS_REVIEW"
        : null;

  async function refreshScanActivity() {
    try {
      onScanChange(await getScan(scan.id));
    } catch {
      // The proposal state remains usable if the optional activity refresh fails.
    }
  }

  async function handleGenerate(finding: Finding) {
    setPendingAction(`generate-${finding.id}`);
    setPatchError(null);
    try {
      const proposal = await generatePatch(finding.id);
      setProposals((current) => ({ ...current, [finding.id]: proposal }));
      await refreshScanActivity();
    } catch (error) {
      setPatchError(error instanceof Error ? error.message : "Patch generation failed.");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleApprove(findingId: string, patchId: string) {
    setPendingAction(`approve-${patchId}`);
    setPatchError(null);
    try {
      const proposal = await approvePatch(patchId);
      setProposals((current) => ({ ...current, [findingId]: proposal }));
      await refreshScanActivity();
    } catch (error) {
      setPatchError(error instanceof Error ? error.message : "Patch approval failed.");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleReject(findingId: string, patchId: string) {
    setPendingAction(`reject-${patchId}`);
    setPatchError(null);
    try {
      const proposal = await rejectPatch(patchId);
      setProposals((current) => ({ ...current, [findingId]: proposal }));
      await refreshScanActivity();
    } catch (error) {
      setPatchError(error instanceof Error ? error.message : "Patch rejection failed.");
    } finally {
      setPendingAction(null);
    }
  }

  if (status === null) {
    return (
      <div className="border-t border-slate-200 py-7">
        <h2 className="text-sm font-semibold text-slate-900">Article 50 Readiness</h2>
        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm font-medium text-slate-800">No confirmed interaction to assess</p>
          <p className="mt-1 text-sm text-slate-500">
            The scan did not establish a complete user-facing AI interaction path.
          </p>
        </div>
      </div>
    );
  }

  const presentation = readinessPresentation(status);
  return (
    <div className="border-t border-slate-200 py-7">
      <h2 className="text-sm font-semibold text-slate-900">Article 50 Readiness</h2>
      <div className={`mt-4 rounded-xl border p-5 sm:p-6 ${presentation.panelClass}`}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className={`text-xs font-semibold uppercase tracking-wider ${presentation.accentClass}`}>
              {presentation.label}
            </p>
            <h3 className="mt-1 text-xl font-semibold text-slate-950">{presentation.title}</h3>
            <p className="mt-2 text-sm text-slate-600">{presentation.description}</p>
          </div>
          <span className={`w-fit rounded-full px-3 py-1 text-xs font-semibold ${presentation.badgeClass}`}>
            {presentation.badge}
          </span>
        </div>
      </div>

      {assessments.length > 0 && (
        <div className="mt-5 space-y-5">
          {assessments.map((assessment) => (
            <AssessmentCard key={assessment.interaction_id} assessment={assessment} scan={scan} />
          ))}
        </div>
      )}

      {scan.findings.length > 0 && (
        <div className="mt-6">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Findings</h3>
          <div className="mt-3 space-y-3">
            {scan.findings.map((finding) => (
              <div key={finding.id} className="space-y-3">
                <FindingCard
                  finding={finding}
                  scan={scan}
                  generating={pendingAction === `generate-${finding.id}`}
                  hasProposal={Boolean(proposals[finding.id])}
                  onGenerate={() => handleGenerate(finding)}
                />
                {proposals[finding.id] && (
                  <PatchReview
                    proposal={proposals[finding.id]}
                    pendingAction={pendingAction}
                    onApprove={() => handleApprove(finding.id, proposals[finding.id].id)}
                    onReject={() => handleReject(finding.id, proposals[finding.id].id)}
                  />
                )}
              </div>
            ))}
          </div>
          {patchError && (
            <p className="mt-3 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">
              {patchError}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function AssessmentCard({
  assessment,
  scan,
}: {
  assessment: TransparencyAssessment;
  scan: Scan;
}) {
  const interaction = scan.ai_interactions.find(
    (candidate) => candidate.id === assessment.interaction_id,
  );
  const disclosureEvidence = assessment.evidence.filter(
    (evidence) => evidence.type === "DISCLOSURE",
  );
  const flow = interaction ? interactionFlow(interaction) : [];

  return (
    <article className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            {assessment.rule_id.replace(/_/g, " ")}
          </p>
          <h3 className="mt-1 text-base font-semibold text-slate-900">
            {interaction?.name ?? "AI interaction"}
          </h3>
        </div>
        <p className="text-sm font-semibold text-slate-800">
          {Math.round(assessment.confidence * 100)}% confidence
        </p>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">{assessment.explanation}</p>

      {flow.length > 0 && (
        <div className="mt-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Reconstructed AI flow
          </p>
          <ol className="mt-3 flex flex-col gap-2 lg:flex-row lg:items-stretch">
            {flow.map((step, index) => (
              <li key={`${step.label}-${step.value}`} className="flex min-w-0 flex-1 items-center gap-2">
                <div className="h-full min-w-0 flex-1 rounded-md border border-slate-200 bg-slate-50 px-3 py-2.5">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    {step.label}
                  </span>
                  <code className="mt-1 block break-all text-[11px] text-slate-800">{step.value}</code>
                </div>
                {index < flow.length - 1 && <span className="text-slate-400">→</span>}
              </li>
            ))}
          </ol>
        </div>
      )}

      <div className="mt-5 rounded-md border border-slate-200 bg-slate-50 p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Disclosure search
        </p>
        <p className="mt-3 text-xs font-medium text-slate-700">Inspected</p>
        <ul className="mt-1 space-y-1">
          {assessment.inspected_files.map((file) => (
            <li key={file}><code className="break-all text-xs text-slate-600">{file}</code></li>
          ))}
        </ul>
        <p className="mt-3 text-xs font-medium text-slate-700">Result</p>
        <p className="mt-1 text-sm text-slate-600">
          {assessment.disclosure_detected
            ? `Disclosure detected: “${assessment.disclosure_text}”`
            : assessment.disclosure_detected === false
              ? "No relevant disclosure detected"
              : "Disclosure context requires manual review"}
        </p>
      </div>

      {disclosureEvidence.length > 0 && (
        <div className="mt-4 space-y-3">
          {disclosureEvidence.map((evidence, index) => (
            <EvidenceItem key={`${evidence.file}-${evidence.line}-${index}`} evidence={evidence} />
          ))}
        </div>
      )}
    </article>
  );
}

function FindingCard({
  finding,
  scan,
  generating,
  hasProposal,
  onGenerate,
}: {
  finding: Finding;
  scan: Scan;
  generating: boolean;
  hasProposal: boolean;
  onGenerate: () => void;
}) {
  const interaction = scan.ai_interactions.find(
    (candidate) => candidate.id === finding.id.replace("article50-", ""),
  );
  return (
    <article className="rounded-lg border border-amber-200 bg-amber-50/50 p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-amber-800">
            {finding.severity} · {finding.status.replace(/_/g, " ")}
          </p>
          <h4 className="mt-1 text-base font-semibold text-slate-900">{finding.title}</h4>
        </div>
        <p className="text-sm font-semibold text-slate-800">
          {Math.round(finding.confidence * 100)}%
        </p>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-600">{finding.explanation}</p>
      <dl className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <dt className="text-xs font-medium text-slate-500">Affected interaction</dt>
          <dd className="mt-1 text-sm text-slate-800">{interaction?.name ?? "AI interaction"}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-slate-500">Affected files</dt>
          <dd className="mt-1 space-y-1">
            {finding.affected_files.map((file) => (
              <code key={file} className="block break-all text-xs text-slate-700">{file}</code>
            ))}
          </dd>
        </div>
      </dl>
      {finding.status === "ACTION_REQUIRED" && finding.remediation_available && !hasProposal && (
        <div className="mt-5 border-t border-amber-200 pt-4">
          <button
            type="button"
            onClick={onGenerate}
            disabled={generating}
            className="rounded-md bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {generating ? "Generating fix…" : "Generate Fix"}
          </button>
          <p className="mt-2 text-xs text-slate-600">
            The agent will prepare a proposal for review. It will not modify your repository.
          </p>
        </div>
      )}
    </article>
  );
}

function PatchReview({
  proposal,
  pendingAction,
  onApprove,
  onReject,
}: {
  proposal: PatchProposal;
  pendingAction: string | null;
  onApprove: () => void;
  onReject: () => void;
}) {
  const awaitingReview = proposal.status === "READY_FOR_REVIEW";
  return (
    <section className="overflow-hidden rounded-lg border border-slate-300 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-5 py-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-indigo-700">
              Proposed Fix
            </p>
            <h4 className="mt-1 text-base font-semibold text-slate-950">{proposal.title}</h4>
          </div>
          <span className="w-fit rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">
            {proposal.status.replace(/_/g, " ")}
          </span>
        </div>
        <p className="mt-3 text-sm leading-6 text-slate-600">{proposal.rationale}</p>
      </div>

      <div className="grid gap-5 px-5 py-5 sm:grid-cols-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Disclosure</p>
          <p className="mt-2 text-sm font-medium text-slate-900">“{proposal.disclosure_text}”</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Affected files
          </p>
          <div className="mt-2 space-y-1">
            {proposal.affected_files.map((file) => (
              <code key={file} className="block break-all text-xs text-slate-700">{file}</code>
            ))}
          </div>
        </div>
      </div>

      <div className="border-t border-slate-200 px-5 py-5">
        <div className="flex items-center justify-between gap-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Diff preview</p>
          <p className="text-xs text-slate-500">{Math.round(proposal.confidence * 100)}% confidence</p>
        </div>
        <DiffViewer diff={proposal.unified_diff} />
      </div>

      <div className="border-t border-slate-200 bg-slate-50 px-5 py-4">
        {awaitingReview ? (
          <>
            <p className="text-sm font-semibold text-slate-900">
              The agent has NOT modified your repository yet.
            </p>
            <p className="mt-1 text-xs text-slate-600">
              Approval records your decision only. Applying and verifying the patch is a later step.
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={onApprove}
                disabled={pendingAction !== null}
                className="rounded-md bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-600 disabled:cursor-not-allowed disabled:bg-slate-400"
              >
                {pendingAction === `approve-${proposal.id}` ? "Approving…" : "Approve Fix"}
              </button>
              <button
                type="button"
                onClick={onReject}
                disabled={pendingAction !== null}
                className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:text-slate-400"
              >
                {pendingAction === `reject-${proposal.id}` ? "Rejecting…" : "Reject"}
              </button>
            </div>
          </>
        ) : proposal.status === "APPROVED" ? (
          <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3">
            <p className="text-sm font-semibold text-emerald-900">Fix approved.</p>
            <p className="mt-1 text-sm text-emerald-800">Ready to apply and verify in Ticket 06.</p>
          </div>
        ) : (
          <div className="rounded-md border border-slate-200 bg-white p-3">
            <p className="text-sm font-semibold text-slate-800">Fix rejected.</p>
            <p className="mt-1 text-sm text-slate-600">The proposal was not applied.</p>
          </div>
        )}
      </div>
    </section>
  );
}

function DiffViewer({ diff }: { diff: string }) {
  return (
    <pre className="mt-3 max-h-96 overflow-auto rounded-md bg-slate-950 py-3 text-xs leading-5 text-slate-200">
      <code>
        {diff.split("\n").map((line, index) => {
          const lineClass = line.startsWith("+") && !line.startsWith("+++")
            ? "bg-emerald-950/70 text-emerald-200"
            : line.startsWith("-") && !line.startsWith("---")
              ? "bg-rose-950/70 text-rose-200"
              : line.startsWith("@@")
                ? "text-sky-300"
                : "";
          return (
            <span key={`${index}-${line}`} className={`block min-w-max px-4 ${lineClass}`}>
              {line || " "}
            </span>
          );
        })}
      </code>
    </pre>
  );
}

function readinessPresentation(status: ReadinessStatus) {
  if (status === "PASS") {
    return {
      label: "Pass",
      title: "Disclosure detected",
      description: "A clear AI transparency disclosure appears in the interaction experience.",
      badge: "Transparency ready",
      panelClass: "border-emerald-200 bg-emerald-50/60",
      accentClass: "text-emerald-700",
      badgeClass: "bg-emerald-100 text-emerald-800",
    };
  }
  if (status === "ACTION_REQUIRED") {
    return {
      label: "Action required",
      title: "Potential transparency gap",
      description: "A confirmed user-facing AI interaction has no clear disclosure in its interface.",
      badge: "Review before release",
      panelClass: "border-amber-300 bg-amber-50",
      accentClass: "text-amber-800",
      badgeClass: "bg-amber-200 text-amber-950",
    };
  }
  return {
    label: "Needs review",
    title: "Manual review recommended",
    description: "The available interface evidence is incomplete or ambiguous.",
    badge: "Context uncertain",
    panelClass: "border-sky-200 bg-sky-50/60",
    accentClass: "text-sky-800",
    badgeClass: "bg-sky-100 text-sky-900",
  };
}

function interactionFlow(interaction: AIInteractionFlow) {
  return [
    { label: "Frontend", value: interaction.frontend_entrypoint },
    { label: "API", value: interaction.api_endpoint },
    { label: "Backend", value: interaction.backend_handler },
    {
      label: "Model",
      value: [interaction.ai_provider, interaction.ai_model].filter(Boolean).join(" · "),
    },
  ].filter((step): step is { label: string; value: string } => Boolean(step.value));
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
  const flow = interactionFlow(interaction);

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
