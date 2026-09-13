import type { HealthResponse } from "../types/api";
import { apiUrl } from "./client";

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(apiUrl("/api/health"), {
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }

  return response.json() as Promise<HealthResponse>;
}
