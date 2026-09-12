import type { ApiStatus } from "../types/api";

interface ApiConnectionStatusProps {
  status: ApiStatus;
}

const labels: Record<ApiStatus, string> = {
  checking: "Checking API",
  connected: "API Connected",
  offline: "API Offline",
};

export function ApiConnectionStatus({ status }: ApiConnectionStatusProps) {
  const dotColor =
    status === "connected"
      ? "bg-emerald-500"
      : status === "offline"
        ? "bg-rose-500"
        : "bg-slate-400";

  return (
    <div className="inline-flex items-center gap-2 text-xs font-medium text-slate-500" role="status">
      <span className={`h-2 w-2 rounded-full ${dotColor}`} aria-hidden="true" />
      {labels[status]}
    </div>
  );
}

