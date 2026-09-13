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
