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

  return response.json() as Promise<Scan>;
}

export async function getScan(scanId: string): Promise<Scan> {
  const response = await fetch(apiUrl(`/api/scans/${encodeURIComponent(scanId)}`), {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw await responseError(response);
  }

  return response.json() as Promise<Scan>;
}
