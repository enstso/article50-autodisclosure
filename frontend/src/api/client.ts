const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export async function responseError(response: Response): Promise<Error> {
  try {
    const payload = (await response.json()) as { detail?: string };
    if (typeof payload.detail === "string") {
      return new Error(payload.detail);
    }
  } catch {
    // The API may be unreachable or return a non-JSON proxy response.
  }
  return new Error(`API request failed with status ${response.status}`);
}
