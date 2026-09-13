import { describe, expect, it } from "vitest";

import type { Finding, Scan, VerificationResult } from "../types/api";
import {
  activityEntries,
  canGenerateFix,
  friendlyAnalysisError,
  isValidRepositoryInput,
  patchPrimaryAction,
  scanReadiness,
  statusLabel,
  verificationHeadline,
  withPendingState,
} from "./presentation";

const finding: Finding = {
  id: "finding-1",
  rule: "ARTICLE_50_1_AI_INTERACTION_DISCLOSURE",
  severity: "MEDIUM",
  title: "Missing AI interaction disclosure",
  explanation: "A disclosure was not found.",
  affected_files: ["frontend/src/Chat.tsx"],
  evidence: [],
  confidence: 0.9,
  status: "ACTION_REQUIRED",
  remediation_available: true,
  patch_proposal_id: null,
  resolution: "OPEN",
};

function scan(status: Scan["status"], findings: Finding[] = []): Scan {
  return {
    id: "scan-1",
    repository_url: "https://github.com/example/ai-chatbot",
    model_mode: "LIVE",
    status,
    summary: null,
    ai_usages: [],
    ai_interactions: [],
    article50_assessments: [],
    findings,
    error: null,
    events: [],
  };
}

describe("presentation state mapping", () => {
  it("uses human-readable status labels", () => {
    expect(statusLabel("ACTION_REQUIRED")).toBe("Action Required");
    expect(statusLabel("READY_FOR_REVIEW")).toBe("Ready for Review");
  });

  it("shows Generate Fix only for an open remediable finding without a proposal", () => {
    expect(canGenerateFix(finding, false)).toBe(true);
    expect(canGenerateFix({ ...finding, status: "PASS", resolution: "RESOLVED" }, false)).toBe(false);
    expect(canGenerateFix(finding, true)).toBe(false);
  });

  it("maps approved and verified patches to one dominant next action", () => {
    expect(patchPrimaryAction("READY_FOR_REVIEW")).toBe("APPROVE");
    expect(patchPrimaryAction("APPROVED")).toBe("APPLY");
    expect(patchPrimaryAction("VERIFIED")).toBe("VIEW_VERIFICATION");
    expect(patchPrimaryAction("REJECTED")).toBeNull();
  });

  it("keeps PASS authoritative after successful verification", () => {
    expect(scanReadiness(scan("PASS", [{ ...finding, status: "PASS", resolution: "RESOLVED" }]))).toBe("PASS");
    const verification = {
      status: "PASSED",
    } as VerificationResult;
    expect(verificationHeadline(verification)).toBe("Fix Verified");
  });
});

describe("demo safety and activity", () => {
  it("accepts only the demo sentinel or a public GitHub repository", () => {
    expect(isValidRepositoryInput("demo://article50-ai-chatbot")).toBe(true);
    expect(isValidRepositoryInput("https://github.com/example/ai-chatbot")).toBe(true);
    expect(isValidRepositoryInput("https://gitlab.com/example/ai-chatbot")).toBe(false);
    expect(isValidRepositoryInput("file:///etc/passwd")).toBe(false);
  });

  it("preserves backend event chronology", () => {
    const events = ["Repository cloned", "AI interaction confirmed", "Verification passed"];
    expect(activityEntries(events)).toEqual([
      { label: events[0], order: 1 },
      { label: events[1], order: 2 },
      { label: events[2], order: 3 },
    ]);
  });

  it("presents Bedrock access failures without exposing raw details", () => {
    expect(friendlyAnalysisError("Amazon Bedrock access was denied.").title).toBe("Live AI model unavailable");
  });

  it("always clears a loading action after an API failure", async () => {
    const states: Array<string | null> = [];
    await expect(
      withPendingState((value) => states.push(value), "approve-patch", async () => {
        throw new Error("network unavailable");
      }),
    ).rejects.toThrow("network unavailable");
    expect(states).toEqual(["approve-patch", null]);
  });
});
