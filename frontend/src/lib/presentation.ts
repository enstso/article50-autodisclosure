import type {
  Finding,
  PatchStatus,
  ReadinessStatus,
  Scan,
  ScanStatus,
  VerificationResult,
} from "../types/api";

export const DEMO_REPOSITORY_URL = "demo://article50-ai-chatbot";

const STATUS_LABELS: Record<ScanStatus | ReadinessStatus | PatchStatus, string> = {
  PENDING: "Pending",
  CLONING: "Cloning",
  ANALYZING: "Analyzing",
  COMPLETED: "Completed",
  PASS: "Pass",
  ACTION_REQUIRED: "Action Required",
  FAILED: "Failed",
  NEEDS_REVIEW: "Needs Review",
  DRAFT: "Draft",
  READY_FOR_REVIEW: "Ready for Review",
  APPROVED: "Approved",
  APPLYING: "Applying",
  APPLIED: "Applied",
  VERIFIED: "Verified",
  REJECTED: "Rejected",
};

export function statusLabel(status: keyof typeof STATUS_LABELS): string {
  return STATUS_LABELS[status];
}

export function scanReadiness(scan: Scan): ReadinessStatus | null {
  if (scan.status === "PASS") return "PASS";
  if (scan.status === "ACTION_REQUIRED") return "ACTION_REQUIRED";
  if (scan.article50_assessments.some((item) => item.status === "NEEDS_REVIEW")) {
    return "NEEDS_REVIEW";
  }
  return null;
}

export function repositoryName(repositoryUrl: string): string {
  if (repositoryUrl === DEMO_REPOSITORY_URL) return "article50-demo-chatbot";
  return repositoryUrl.replace(/\.git$/, "").split("/").filter(Boolean).at(-1) ?? repositoryUrl;
}

export function isValidRepositoryInput(value: string): boolean {
  if (value === DEMO_REPOSITORY_URL) return true;
  try {
    const url = new URL(value);
    const parts = url.pathname.split("/").filter(Boolean);
    return (
      url.protocol === "https:" &&
      url.hostname.toLowerCase() === "github.com" &&
      !url.username &&
      !url.password &&
      !url.port &&
      !url.search &&
      !url.hash &&
      parts.length === 2 &&
      parts.every(Boolean)
    );
  } catch {
    return false;
  }
}

export function canGenerateFix(finding: Finding, hasProposal: boolean): boolean {
  return (
    finding.status === "ACTION_REQUIRED" &&
    finding.resolution === "OPEN" &&
    finding.remediation_available &&
    !hasProposal
  );
}

export type PatchPrimaryAction = "APPROVE" | "APPLY" | "VIEW_VERIFICATION" | null;

export function patchPrimaryAction(status: PatchStatus): PatchPrimaryAction {
  if (status === "READY_FOR_REVIEW") return "APPROVE";
  if (status === "APPROVED") return "APPLY";
  if (status === "VERIFIED" || status === "APPLIED") return "VIEW_VERIFICATION";
  return null;
}

export function verificationHeadline(verification: VerificationResult): string {
  if (verification.status === "PASSED") return "Fix Verified";
  if (verification.status === "FAILED") return "Patch applied, but verification failed.";
  return "Patch applied; manual verification required.";
}

export function activityEntries(events: string[]) {
  return events.map((label, index) => ({ label, order: index + 1 }));
}

export function friendlyAnalysisError(message: string | null): {
  title: string;
  detail: string;
} {
  const detail = message || "We could not analyze this repository.";
  if (/bedrock|model|authentication|access was denied/i.test(detail)) {
    return {
      title: "Live AI model unavailable",
      detail:
        "The repository scan could not complete its model-based analysis. Try Demo Repository or retry when Amazon Bedrock access is available.",
    };
  }
  return {
    title: "Repository analysis failed",
    detail: "We could not analyze this repository. Check that it is public, then try again.",
  };
}

export async function withPendingState<T>(
  setPending: (value: string | null) => void,
  key: string,
  action: () => Promise<T>,
): Promise<T> {
  setPending(key);
  try {
    return await action();
  } finally {
    setPending(null);
  }
}
