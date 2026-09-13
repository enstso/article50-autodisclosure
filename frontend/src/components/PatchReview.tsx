import { verificationHeadline } from "../lib/presentation";
import type { PatchProposal, VerificationResult } from "../types/api";
import { StatusBadge } from "./StatusBadge";

interface PatchReviewProps {
  proposal: PatchProposal;
  verification?: VerificationResult;
  pendingAction: string | null;
  onApprove: () => void;
  onReject: () => void;
  onApply: () => void;
}

export function PatchReview({
  proposal,
  verification,
  pendingAction,
  onApprove,
  onReject,
  onApply,
}: PatchReviewProps) {
  const reviewing = proposal.status === "READY_FOR_REVIEW";
  const applying = pendingAction === `apply-${proposal.id}`;

  return (
    <article className="overflow-hidden rounded-2xl border border-violet-200 bg-white shadow-panel">
      <div className="border-b border-slate-200 bg-gradient-to-r from-violet-50 to-white px-6 py-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="eyebrow text-violet-700">Proposed Remediation</p>
            <h3 className="mt-1 text-xl font-bold tracking-tight text-slate-950">{proposal.title}</h3>
          </div>
          <StatusBadge status={proposal.status} pulse={proposal.status === "APPLYING"} />
        </div>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">{proposal.rationale}</p>
      </div>

      <div className="grid gap-4 px-6 py-5 md:grid-cols-2">
        <div className="rounded-xl border border-violet-100 bg-violet-50/60 p-4">
          <p className="eyebrow text-violet-700">Disclosure</p>
          <blockquote className="mt-2 text-base font-semibold leading-6 text-slate-950">
            “{proposal.disclosure_text}”
          </blockquote>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <p className="eyebrow">Affected file</p>
          {proposal.affected_files.map((file) => (
            <code key={file} className="mt-2 block break-all text-xs font-semibold text-slate-700">{file}</code>
          ))}
          <p className="mt-3 text-xs text-slate-500">{Math.round(proposal.confidence * 100)}% evidence confidence</p>
        </div>
      </div>

      <div className="border-t border-slate-200 px-6 py-5">
        <div className="flex items-center justify-between gap-4">
          <p className="eyebrow">Diff Preview</p>
          <span className="text-xs text-slate-500">Added and removed lines highlighted</span>
        </div>
        <DiffViewer diff={proposal.unified_diff} />
      </div>

      <div className="border-t border-slate-200 bg-slate-50 px-6 py-5">
        {reviewing ? (
          <div>
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
              <p className="text-sm font-bold text-amber-950">Human approval required before code changes.</p>
              <p className="mt-1 text-sm leading-5 text-amber-800">
                The agent has proposed a remediation. No source code has been modified yet.
              </p>
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              <button type="button" onClick={onApprove} disabled={pendingAction !== null} className="primary-button">
                {pendingAction === `approve-${proposal.id}` ? "Approving…" : "Approve Fix"}
              </button>
              <button type="button" onClick={onReject} disabled={pendingAction !== null} className="secondary-button">
                {pendingAction === `reject-${proposal.id}` ? "Rejecting…" : "Reject"}
              </button>
            </div>
          </div>
        ) : proposal.status === "APPROVED" ? (
          applying ? (
            <ApplyProgress />
          ) : (
            <div>
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                <p className="text-sm font-bold text-emerald-950">Fix approved.</p>
                <p className="mt-1 text-sm text-emerald-800">
                  The agent can now apply the patch and verify the Article 50 readiness result.
                </p>
              </div>
              <button type="button" onClick={onApply} disabled={pendingAction !== null} className="primary-button mt-4">
                Apply &amp; Verify
              </button>
              <p className="mt-3 text-xs text-slate-500">
                Verification uses static repository analysis. Repository code is not executed.
              </p>
            </div>
          )
        ) : verification ? (
          <VerificationComparison proposal={proposal} verification={verification} />
        ) : (
          <PatchTerminalState proposal={proposal} />
        )}
      </div>
    </article>
  );
}

function ApplyProgress() {
  const steps = [
    "Applying approved patch...",
    "Re-scanning affected interaction...",
    "Checking AI disclosure...",
    "Verifying Article 50 readiness...",
  ];
  return (
    <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-4" role="status">
      <div className="flex items-center gap-3">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-700" />
        <p className="text-sm font-bold text-indigo-950">Apply &amp; Verify in progress</p>
      </div>
      <ol className="mt-4 grid gap-2 sm:grid-cols-2">
        {steps.map((step) => (
          <li key={step} className="flex items-center gap-2 text-xs text-indigo-800">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-indigo-500" />{step}
          </li>
        ))}
      </ol>
    </div>
  );
}

function VerificationComparison({ proposal, verification }: { proposal: PatchProposal; verification: VerificationResult }) {
  const passed = verification.status === "PASSED";
  const disclosure = verification.evidence.find((item) => item.type === "DISCLOSURE");
  return (
    <section id="verification" className={`scroll-mt-24 rounded-2xl border p-5 ${passed ? "border-emerald-300 bg-emerald-50" : "border-amber-300 bg-amber-50"}`}>
      <div className="flex items-start gap-3">
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-lg font-black text-white ${passed ? "bg-emerald-600" : "bg-amber-500"}`} aria-hidden="true">
          {passed ? "✓" : "!"}
        </span>
        <div>
          <p className={`text-lg font-bold ${passed ? "text-emerald-950" : "text-amber-950"}`}>{verificationHeadline(verification)}</p>
          <p className="mt-1 text-sm leading-6 text-slate-700">{verification.explanation}</p>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-rose-200 bg-white p-4">
          <p className="eyebrow text-rose-700">Before</p>
          <p className="mt-2 text-xl font-black text-rose-700">ACTION REQUIRED</p>
          <p className="mt-2 text-sm text-slate-600">× No explicit AI disclosure detected</p>
        </div>
        <div className={`rounded-xl border bg-white p-4 ${passed ? "border-emerald-300" : "border-amber-300"}`}>
          <p className={`eyebrow ${passed ? "text-emerald-700" : "text-amber-700"}`}>After</p>
          <p className={`mt-2 text-xl font-black ${passed ? "text-emerald-700" : "text-amber-700"}`}>
            {verification.new_readiness_status.replace(/_/g, " ")}
          </p>
          <p className="mt-2 text-sm text-slate-600">
            {verification.disclosure_detected ? `✓ “${proposal.disclosure_text}”` : "× No qualifying AI disclosure detected"}
          </p>
        </div>
      </div>
      {disclosure && (
        <div className="mt-4 rounded-lg border border-emerald-200 bg-white px-4 py-3 text-xs text-slate-600">
          <span className="font-bold text-emerald-700">AI disclosure detected</span>
          <code className="ml-2 break-all">{disclosure.file}{disclosure.line ? `:${disclosure.line}` : ""}</code>
        </div>
      )}
    </section>
  );
}

function PatchTerminalState({ proposal }: { proposal: PatchProposal }) {
  const failed = proposal.status === "FAILED";
  return (
    <div className={`rounded-xl border p-4 ${failed ? "border-rose-200 bg-rose-50" : "border-slate-200 bg-white"}`}>
      <p className="text-sm font-bold text-slate-900">{failed ? "Patch application failed." : "Fix rejected."}</p>
      <p className="mt-1 text-sm text-slate-600">
        {failed ? "The safety snapshot preserved the approved source state." : "The proposal was not applied."}
      </p>
    </div>
  );
}

function DiffViewer({ diff }: { diff: string }) {
  return (
    <pre className="mt-3 max-h-[28rem] overflow-auto rounded-xl border border-slate-800 bg-slate-950 py-3 font-mono text-[11px] leading-5 text-slate-300">
      <code>
        {diff.split("\n").map((line, index) => {
          const added = line.startsWith("+") && !line.startsWith("+++");
          const removed = line.startsWith("-") && !line.startsWith("---");
          const hunk = line.startsWith("@@");
          const tone = added ? "bg-emerald-950/80 text-emerald-200" : removed ? "bg-rose-950/80 text-rose-200" : hunk ? "text-sky-300" : "";
          return (
            <span key={`${index}-${line}`} className={`grid grid-cols-[2.25rem_1fr] px-3 ${tone}`}>
              <span className="select-none border-r border-slate-800 pr-2 text-right text-slate-600">{index + 1}</span>
              <span className="whitespace-pre-wrap break-all pl-3">{line || " "}</span>
            </span>
          );
        })}
      </code>
    </pre>
  );
}
