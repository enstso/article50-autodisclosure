import type { PatchApplyResponse, PatchProposal, VerificationResult } from "../types/api";
import { apiUrl, responseError } from "./client";

async function patchRequest<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: {
      Accept: "application/json",
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    throw await responseError(response);
  }
  return response.json() as Promise<T>;
}

export async function getPatch(patchId: string): Promise<PatchProposal> {
  const response = await fetch(apiUrl(`/api/patches/${encodeURIComponent(patchId)}`), {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw await responseError(response);
  }
  return response.json() as Promise<PatchProposal>;
}

export async function getPatchVerification(patchId: string): Promise<VerificationResult> {
  const response = await fetch(
    apiUrl(`/api/patches/${encodeURIComponent(patchId)}/verification`),
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw await responseError(response);
  }
  return response.json() as Promise<VerificationResult>;
}

export function generatePatch(findingId: string): Promise<PatchProposal> {
  return patchRequest<PatchProposal>(`/api/findings/${encodeURIComponent(findingId)}/patch`);
}

export function approvePatch(patchId: string): Promise<PatchProposal> {
  return patchRequest<PatchProposal>(`/api/patches/${encodeURIComponent(patchId)}/approve`);
}

export function rejectPatch(patchId: string, reason?: string): Promise<PatchProposal> {
  return patchRequest<PatchProposal>(
    `/api/patches/${encodeURIComponent(patchId)}/reject`,
    reason ? { reason } : undefined,
  );
}

export function applyPatch(patchId: string): Promise<PatchApplyResponse> {
  return patchRequest<PatchApplyResponse>(
    `/api/patches/${encodeURIComponent(patchId)}/apply`,
  );
}
