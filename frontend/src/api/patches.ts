import type { PatchProposal } from "../types/api";
import { apiUrl, responseError } from "./client";

async function patchRequest(path: string, body?: object): Promise<PatchProposal> {
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
  return response.json() as Promise<PatchProposal>;
}

export function generatePatch(findingId: string): Promise<PatchProposal> {
  return patchRequest(`/api/findings/${encodeURIComponent(findingId)}/patch`);
}

export function approvePatch(patchId: string): Promise<PatchProposal> {
  return patchRequest(`/api/patches/${encodeURIComponent(patchId)}/approve`);
}

export function rejectPatch(patchId: string, reason?: string): Promise<PatchProposal> {
  return patchRequest(
    `/api/patches/${encodeURIComponent(patchId)}/reject`,
    reason ? { reason } : undefined,
  );
}
