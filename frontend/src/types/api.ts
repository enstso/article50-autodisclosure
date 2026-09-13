export type ApiStatus = "checking" | "connected" | "offline";

export interface HealthResponse {
  status: "ok";
  service: string;
}

export type ScanStatus =
  | "PENDING"
  | "CLONING"
  | "ANALYZING"
  | "COMPLETED"
  | "ACTION_REQUIRED"
  | "PASS"
  | "FAILED";

export interface RepositorySummary {
  languages: string[];
  frameworks: string[];
  architecture_summary: string;
  important_files: string[];
  potential_ai_integrations: string[];
}

export type EvidenceType =
  | "AI_USAGE"
  | "USER_INTERACTION"
  | "API_ROUTE"
  | "BACKEND_HANDLER"
  | "MODEL_CALL"
  | "MODEL_CONFIGURATION"
  | "DISCLOSURE"
  | "DISCLOSURE_ABSENCE"
  | "UI_CONTEXT";

export interface Evidence {
  file: string;
  line: number | null;
  snippet: string;
  type: EvidenceType;
}

export interface AIUsage {
  provider: string | null;
  sdk: string | null;
  model: string | null;
  file: string;
  line: number | null;
  purpose: string | null;
  evidence: Evidence[];
  confidence: number;
}

export interface AIInteractionFlow {
  id: string;
  name: string;
  user_facing: boolean;
  frontend_entrypoint: string | null;
  api_endpoint: string | null;
  backend_handler: string | null;
  ai_provider: string | null;
  ai_model: string | null;
  flow_summary: string;
  evidence: Evidence[];
  confidence: number;
}

export type ReadinessStatus = "PASS" | "ACTION_REQUIRED" | "NEEDS_REVIEW";

export interface TransparencyAssessment {
  interaction_id: string;
  rule_id: string;
  status: ReadinessStatus;
  disclosure_detected: boolean | null;
  disclosure_text: string | null;
  disclosure_file: string | null;
  disclosure_line: number | null;
  explanation: string;
  evidence: Evidence[];
  inspected_files: string[];
  confidence: number;
}

export interface Finding {
  id: string;
  rule: string;
  severity: string;
  title: string;
  explanation: string;
  affected_files: string[];
  evidence: Evidence[];
  confidence: number;
  status: ReadinessStatus;
  remediation_available: boolean;
  patch_proposal_id: string | null;
  resolution: "OPEN" | "RESOLVED";
}

export type PatchStatus =
  | "DRAFT"
  | "READY_FOR_REVIEW"
  | "APPROVED"
  | "APPLYING"
  | "APPLIED"
  | "VERIFIED"
  | "FAILED"
  | "REJECTED";

export interface PatchProposal {
  id: string;
  scan_id: string;
  finding_id: string;
  status: PatchStatus;
  title: string;
  rationale: string;
  affected_files: string[];
  disclosure_text: string | null;
  unified_diff: string;
  original_snippets: Evidence[];
  proposed_snippets: Evidence[];
  confidence: number;
  created_at: string;
  approved_at: string | null;
  applied_at: string | null;
  verified_at: string | null;
  modified_files: string[];
  rejected_at: string | null;
  rejection_reason: string | null;
}

export type VerificationStatus = "PENDING" | "PASSED" | "FAILED" | "NEEDS_REVIEW";

export interface VerificationResult {
  id: string;
  patch_id: string;
  scan_id: string;
  finding_id: string;
  status: VerificationStatus;
  previous_readiness_status: ReadinessStatus;
  new_readiness_status: ReadinessStatus;
  disclosure_detected: boolean | null;
  explanation: string;
  evidence: Evidence[];
  verified_at: string;
}

export interface PatchApplyResponse {
  patch_id: string;
  patch_status: PatchStatus;
  verification: VerificationResult;
}

export interface Scan {
  id: string;
  repository_url: string;
  status: ScanStatus;
  summary: RepositorySummary | null;
  ai_usages: AIUsage[];
  ai_interactions: AIInteractionFlow[];
  article50_assessments: TransparencyAssessment[];
  findings: Finding[];
  error: string | null;
  events: string[];
}
