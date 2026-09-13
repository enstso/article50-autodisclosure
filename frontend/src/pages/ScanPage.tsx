import { type ReactNode, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import {
  applyPatch,
  approvePatch,
  generatePatch,
  getPatch,
  getPatchVerification,
  rejectPatch,
} from "../api/patches";
import { getScan, normalizeScan } from "../api/scans";
import { AgentTimeline } from "../components/AgentTimeline";
import { AppShell } from "../components/AppShell";
import { EvidenceList } from "../components/EvidenceList";
import { InteractionFlow } from "../components/InteractionFlow";
import { PatchReview } from "../components/PatchReview";
import { ReadinessCard } from "../components/ReadinessCard";
import { StatusBadge } from "../components/StatusBadge";
import {
  canGenerateFix,
  friendlyAnalysisError,
  repositoryName,
  scanReadiness,
  withPendingState,
} from "../lib/presentation";
import type { Finding, PatchProposal, Scan, VerificationResult } from "../types/api";

interface ScanRouteState {
  initialScan?: Scan;
}

export function ScanPage() {
  const { scanId } = useParams();
  const location = useLocation();
  const routeScan = (location.state as ScanRouteState | null)?.initialScan;
  const initialScan = routeScan ? normalizeScan(routeScan) : null;
  const [scan, setScan] = useState<Scan | null>(initialScan);
  const [loading, setLoading] = useState(!initialScan);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!scanId) {
      setLoadError("Scan not found.");
      setLoading(false);
      return;
    }
    let active = true;
    getScan(scanId)
      .then((result) => {
        if (active) {
          setScan(result);
          setLoadError(null);
        }
      })
      .catch((error: unknown) => {
        if (active) setLoadError(error instanceof Error ? error.message : "Scan not found.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [scanId]);

  if (loading && !scan) {
    return (
      <AppShell>
        <main className="mx-auto max-w-7xl px-5 py-16 sm:px-8">
          <ResultSkeleton />
        </main>
      </AppShell>
    );
  }

  if (!scan || loadError) {
    return (
      <AppShell>
        <main className="mx-auto max-w-3xl px-5 py-24 text-center sm:px-8">
          <div className="rounded-2xl border border-rose-200 bg-white p-8 shadow-panel">
            <p className="eyebrow text-rose-700">Result unavailable</p>
            <h1 className="mt-2 text-2xl font-bold text-slate-950">We could not restore this analysis.</h1>
            <p className="mt-3 text-sm text-slate-600">{loadError || "Scan not found."}</p>
            <Link to="/" className="primary-button mt-6">Start New Analysis</Link>
          </div>
        </main>
      </AppShell>
    );
  }

  return <ScanResult scan={scan} onScanChange={setScan} />;
}

function ScanResult({ scan, onScanChange }: { scan: Scan; onScanChange: (scan: Scan) => void }) {
  const remediation = useRemediation(scan, onScanChange);
  const confirmedInteractions = scan.ai_interactions.filter((item) => item.user_facing);
  const disclosureEvidence = scan.article50_assessments.flatMap((assessment) =>
    assessment.evidence.filter((evidence) => evidence.type === "DISCLOSURE"),
  );

  if (scan.status === "FAILED") {
    const error = friendlyAnalysisError(scan.error);
    return (
      <AppShell modelMode={scan.model_mode}>
        <main className="mx-auto max-w-5xl px-5 py-12 sm:px-8 sm:py-16">
          <ScanHeader scan={scan} />
          <section className="mt-8 rounded-2xl border border-rose-200 bg-white p-8 shadow-panel" role="alert">
            <p className="eyebrow text-rose-700">Analysis stopped safely</p>
            <h1 className="mt-2 text-2xl font-bold text-slate-950">{error.title}</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">{error.detail}</p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link to="/" className="primary-button">Try Again</Link>
              <Link to="/" state={{ useDemo: true }} className="secondary-button">Try Demo Repository</Link>
            </div>
          </section>
          {scan.events.length > 0 && <div className="mt-8"><AgentTimeline events={scan.events} /></div>}
        </main>
      </AppShell>
    );
  }

  return (
    <AppShell modelMode={scan.model_mode}>
      <main id="result" className="mx-auto max-w-7xl px-5 py-8 sm:px-8 sm:py-12">
        <ScanHeader scan={scan} />

        <div className="mt-7 space-y-7">
          <ReadinessCard scan={scan} />

          <FindingSection
            scan={scan}
            proposals={remediation.proposals}
            pendingAction={remediation.pendingAction}
            onGenerate={remediation.generate}
          />

          {remediation.error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-4" role="alert">
              <p className="text-sm font-bold text-rose-950">Remediation action failed</p>
              <p className="mt-1 text-sm text-rose-800">{remediation.error}</p>
              <p className="mt-2 text-xs text-rose-700">The action is available again. Review the message and retry.</p>
            </div>
          )}

          {confirmedInteractions.length === 0 ? (
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-panel">
              <p className="eyebrow">AI Interaction</p>
              <h2 className="mt-2 text-xl font-bold text-slate-950">No direct user-facing AI interaction detected.</h2>
              <p className="mt-2 text-sm text-slate-600">No Article 50 interaction disclosure finding was generated.</p>
            </section>
          ) : (
            confirmedInteractions.map((interaction) => (
              <InteractionFlow key={interaction.id} interaction={interaction} />
            ))
          )}

          {disclosureEvidence.length > 0 && remediation.proposalList.length === 0 && (
            <section className="rounded-2xl border border-emerald-200 bg-white p-6 shadow-panel">
              <p className="eyebrow text-emerald-700">Transparency Disclosure</p>
              <h2 className="mt-1 text-xl font-bold text-slate-950">Disclosure evidence</h2>
              <div className="mt-5"><EvidenceList evidence={disclosureEvidence} /></div>
            </section>
          )}

          {remediation.proposalList.length > 0 && (
            <section id="remediation" className="scroll-mt-24 space-y-4">
              <div>
                <p className="eyebrow">Human Approval</p>
                <h2 className="mt-1 text-2xl font-bold tracking-tight text-slate-950">Review the recommended remediation</h2>
              </div>
              {remediation.proposalList.map((proposal) => (
                <PatchReview
                  key={proposal.id}
                  proposal={proposal}
                  verification={remediation.verifications[proposal.finding_id]}
                  pendingAction={remediation.pendingAction}
                  onApprove={() => remediation.approve(proposal.finding_id, proposal.id)}
                  onReject={() => remediation.reject(proposal.finding_id, proposal.id)}
                  onApply={() => remediation.apply(proposal.finding_id, proposal.id)}
                />
              ))}
            </section>
          )}

          <RepositoryDetails scan={scan} />
          <AgentTimeline events={scan.events} />
        </div>
      </main>
    </AppShell>
  );
}

function ScanHeader({ scan }: { scan: Scan }) {
  const readiness = scanReadiness(scan);
  const title = repositoryName(scan.repository_url);
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="eyebrow">Repository</p>
            {scan.model_mode === "DEMO" && <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-violet-700">Demo repository</span>}
          </div>
          <h1 className="mt-1 truncate text-2xl font-black tracking-tight text-slate-950">{title}</h1>
          <p className="mt-1 truncate text-xs text-slate-500">{scan.repository_url}</p>
        </div>
        <dl className="grid grid-cols-3 gap-2 sm:gap-3">
          <Metric label="Status"><StatusBadge status={readiness ?? scan.status} /></Metric>
          <Metric label="AI interactions" value={String(scan.ai_interactions.filter((item) => item.user_facing).length)} />
          <Metric label="Article 50 findings" value={String(scan.findings.filter((item) => item.resolution === "OPEN").length)} />
        </dl>
      </div>
    </section>
  );
}

function Metric({ label, value, children }: { label: string; value?: string; children?: ReactNode }) {
  return (
    <div className="min-w-0 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 sm:px-4">
      <dt className="truncate text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}</dt>
      <dd className="mt-2 text-xl font-black text-slate-950">{children ?? value}</dd>
    </div>
  );
}

function FindingSection({ scan, proposals, pendingAction, onGenerate }: {
  scan: Scan;
  proposals: Record<string, PatchProposal>;
  pendingAction: string | null;
  onGenerate: (finding: Finding) => void;
}) {
  if (scan.findings.length === 0) return null;
  return (
    <section>
      <div className="mb-4">
        <p className="eyebrow">Finding</p>
        <h2 className="mt-1 text-2xl font-bold tracking-tight text-slate-950">What needs attention</h2>
      </div>
      <div className="space-y-4">
        {scan.findings.map((finding) => {
          const resolved = finding.resolution === "RESOLVED";
          const hasProposal = Boolean(proposals[finding.id]);
          const canGenerate = canGenerateFix(finding, hasProposal);
          return (
            <article key={finding.id} className={`rounded-2xl border p-6 shadow-sm ${resolved ? "border-emerald-200 bg-emerald-50/50" : "border-amber-300 bg-white"}`}>
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge status={resolved ? "PASS" : finding.status} />
                    <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-600">Severity {finding.severity.toLowerCase()}</span>
                  </div>
                  <h3 className="mt-4 text-xl font-bold text-slate-950">{resolved ? "AI interaction disclosure resolved" : finding.title}</h3>
                </div>
                <span className="text-sm font-bold text-slate-500">{Math.round(finding.confidence * 100)}% confidence</span>
              </div>
              <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_0.75fr]">
                <div>
                  <p className="eyebrow">Why this matters</p>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{finding.explanation}</p>
                </div>
                <div>
                  <p className="eyebrow">Affected file</p>
                  <div className="mt-2 space-y-1">
                    {finding.affected_files.map((file) => <code key={file} className="block break-all text-xs font-semibold text-indigo-700">{file}</code>)}
                  </div>
                </div>
              </div>
              {canGenerate && (
                <div className="mt-5 border-t border-slate-200 pt-5">
                  <button type="button" onClick={() => onGenerate(finding)} disabled={pendingAction !== null} className="primary-button">
                    {pendingAction === `generate-${finding.id}` ? "Generating Remediation…" : "Generate Fix"}
                  </button>
                  <p className="mt-2 text-xs text-slate-500">Creates a reviewable proposal. No source code is changed.</p>
                </div>
              )}
              {hasProposal && !resolved && <p className="mt-5 border-t border-slate-200 pt-4 text-xs font-semibold text-violet-700">Remediation prepared below for human review ↓</p>}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function RepositoryDetails({ scan }: { scan: Scan }) {
  if (!scan.summary) return null;
  return (
    <details className="group rounded-2xl border border-slate-200 bg-white shadow-sm">
      <summary className="flex cursor-pointer list-none items-center justify-between px-6 py-5 font-bold text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500">
        Repository architecture
        <span className="text-slate-400 transition group-open:rotate-45" aria-hidden="true">+</span>
      </summary>
      <div className="grid gap-6 border-t border-slate-200 px-6 py-5 md:grid-cols-3">
        <div className="md:col-span-2">
          <p className="eyebrow">Summary</p>
          <p className="mt-2 text-sm leading-6 text-slate-600">{scan.summary.architecture_summary}</p>
        </div>
        <div>
          <p className="eyebrow">Stack</p>
          <p className="mt-2 text-sm text-slate-600">{[...scan.summary.languages, ...scan.summary.frameworks].join(" · ") || "None detected"}</p>
        </div>
        <div className="md:col-span-3">
          <p className="eyebrow">Important files</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {scan.summary.important_files.map((file) => <code key={file} className="rounded-md bg-slate-100 px-2 py-1 text-[11px] text-slate-600">{file}</code>)}
          </div>
        </div>
      </div>
    </details>
  );
}

function useRemediation(scan: Scan, onScanChange: (scan: Scan) => void) {
  const [proposals, setProposals] = useState<Record<string, PatchProposal>>({});
  const [verifications, setVerifications] = useState<Record<string, VerificationResult>>({});
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const patchIds = useMemo(
    () => scan.findings.map((finding) => finding.patch_proposal_id).filter(Boolean).join(","),
    [scan.findings],
  );

  useEffect(() => {
    const linked = scan.findings.filter((finding) => finding.patch_proposal_id);
    if (linked.length === 0) return;
    let active = true;
    Promise.all(
      linked.map(async (finding) => {
        const proposal = await getPatch(finding.patch_proposal_id!);
        let verification: VerificationResult | undefined;
        if (proposal.status === "APPLIED" || proposal.status === "VERIFIED") {
          try {
            verification = await getPatchVerification(proposal.id);
          } catch {
            // A patch can briefly be APPLIED before its verification record is stored.
          }
        }
        return { findingId: finding.id, proposal, verification };
      }),
    )
      .then((records) => {
        if (!active) return;
        setProposals(Object.fromEntries(records.map((record) => [record.findingId, record.proposal])));
        setVerifications(Object.fromEntries(records.filter((record) => record.verification).map((record) => [record.findingId, record.verification!])));
      })
      .catch(() => {
        if (active) setError("The saved remediation state could not be restored.");
      });
    return () => {
      active = false;
    };
  }, [patchIds, scan.findings]);

  async function refreshScan() {
    try {
      onScanChange(await getScan(scan.id));
    } catch {
      // The current result remains usable when an optional refresh fails.
    }
  }

  async function run(key: string, action: () => Promise<void>, fallback: string) {
    setError(null);
    try {
      await withPendingState(setPendingAction, key, action);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : fallback);
    }
  }

  function generate(finding: Finding) {
    void run(`generate-${finding.id}`, async () => {
      const proposal = await generatePatch(finding.id);
      setProposals((current) => ({ ...current, [finding.id]: proposal }));
      await refreshScan();
      window.setTimeout(() => document.getElementById("remediation")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
    }, "Remediation generation failed.");
  }

  function approve(findingId: string, patchId: string) {
    void run(`approve-${patchId}`, async () => {
      const proposal = await approvePatch(patchId);
      setProposals((current) => ({ ...current, [findingId]: proposal }));
      await refreshScan();
    }, "Patch approval failed.");
  }

  function reject(findingId: string, patchId: string) {
    void run(`reject-${patchId}`, async () => {
      const proposal = await rejectPatch(patchId);
      setProposals((current) => ({ ...current, [findingId]: proposal }));
      await refreshScan();
    }, "Patch rejection failed.");
  }

  function apply(findingId: string, patchId: string) {
    void run(`apply-${patchId}`, async () => {
      const result = await applyPatch(patchId);
      const proposal = await getPatch(patchId);
      setProposals((current) => ({ ...current, [findingId]: proposal }));
      setVerifications((current) => ({ ...current, [findingId]: result.verification }));
      await refreshScan();
      window.setTimeout(() => document.getElementById("verification")?.scrollIntoView({ behavior: "smooth", block: "center" }), 0);
    }, "Patch application failed.");
  }

  return {
    proposals,
    verifications,
    pendingAction,
    error,
    generate,
    approve,
    reject,
    apply,
    proposalList: Object.values(proposals),
  };
}

function ResultSkeleton() {
  return (
    <div className="animate-pulse space-y-6" role="status">
      <span className="sr-only">Restoring analysis result…</span>
      <div className="h-32 rounded-2xl bg-slate-200" />
      <div className="h-64 rounded-2xl bg-slate-200" />
      <div className="h-48 rounded-2xl bg-slate-200" />
    </div>
  );
}
