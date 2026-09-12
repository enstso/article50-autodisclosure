export type ApiStatus = "checking" | "connected" | "offline";

export interface HealthResponse {
  status: "ok";
  service: string;
}

