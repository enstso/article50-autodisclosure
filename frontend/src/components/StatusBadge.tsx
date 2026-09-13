import { statusLabel } from "../lib/presentation";
import type { PatchStatus, ReadinessStatus, ScanStatus } from "../types/api";

type Status = ScanStatus | ReadinessStatus | PatchStatus;

const toneByStatus: Record<Status, string> = {
  PENDING: "border-slate-200 bg-slate-100 text-slate-700",
  CLONING: "border-indigo-200 bg-indigo-50 text-indigo-700",
  ANALYZING: "border-indigo-200 bg-indigo-50 text-indigo-700",
  COMPLETED: "border-slate-200 bg-slate-100 text-slate-700",
  PASS: "border-emerald-200 bg-emerald-50 text-emerald-700",
  ACTION_REQUIRED: "border-amber-300 bg-amber-50 text-amber-800",
  NEEDS_REVIEW: "border-sky-200 bg-sky-50 text-sky-700",
  FAILED: "border-rose-200 bg-rose-50 text-rose-700",
  DRAFT: "border-slate-200 bg-slate-100 text-slate-700",
  READY_FOR_REVIEW: "border-violet-200 bg-violet-50 text-violet-700",
  APPROVED: "border-indigo-200 bg-indigo-50 text-indigo-700",
  APPLYING: "border-indigo-200 bg-indigo-50 text-indigo-700",
  APPLIED: "border-sky-200 bg-sky-50 text-sky-700",
  VERIFIED: "border-emerald-200 bg-emerald-50 text-emerald-700",
  REJECTED: "border-slate-300 bg-slate-100 text-slate-600",
};

export function StatusBadge({ status, pulse = false }: { status: Status; pulse?: boolean }) {
  return (
    <span className={`inline-flex w-fit items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-extrabold uppercase tracking-[0.12em] ${toneByStatus[status]}`}>
      {pulse && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}
      {statusLabel(status)}
    </span>
  );
}
