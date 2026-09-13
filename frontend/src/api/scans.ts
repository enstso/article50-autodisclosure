import type { Scan } from "../types/api";
import { apiUrl, responseError } from "./client";

export async function createScan(repositoryUrl: string): Promise<Scan> {
  const response = await fetch(apiUrl("/api/scans"), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ repository_url: repositoryUrl }),
  });

  if (!response.ok) {
    throw await responseError(response);
  }

  return normalizeScan(await response.json());
}

export async function getScan(scanId: string): Promise<Scan> {
  const response = await fetch(apiUrl(`/api/scans/${encodeURIComponent(scanId)}`), {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw await responseError(response);
  }

  return normalizeScan(await response.json());
}

export function normalizeScan(payload: unknown): Scan {
  const scan = payload as Scan;
  return {
    ...scan,
    model_mode: scan.model_mode ?? "LIVE",
    ai_usages: scan.ai_usages ?? [],
    ai_interactions: scan.ai_interactions ?? [],
    article50_assessments: scan.article50_assessments ?? [],
    findings: scan.findings ?? [],
    events: scan.events ?? [],
  };
}
