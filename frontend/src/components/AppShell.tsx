import { ReactNode, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getHealth } from "../api/health";
import type { ApiStatus, HealthResponse, ModelMode } from "../types/api";
import { ApiConnectionStatus } from "./ApiConnectionStatus";

interface AppShellProps {
  children: ReactNode;
  modelMode?: ModelMode;
}

export function AppShell({ children, modelMode }: AppShellProps) {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal)
      .then((response) => {
        setHealth(response);
        setApiStatus("connected");
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          setApiStatus("offline");
        }
      });
    return () => controller.abort();
  }, []);

  const activeMode = modelMode ?? health?.model_mode;

  return (
    <div className="min-h-screen bg-canvas text-slate-950">
      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/90 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-5 sm:px-8">
          <Link to="/" className="group flex min-w-0 items-center gap-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-4">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-950 text-[11px] font-black tracking-tight text-white shadow-sm transition group-hover:bg-indigo-700">
              A50
            </span>
            <span className="truncate text-sm font-bold tracking-tight text-slate-950">
              Article 50 AutoDisclosure
            </span>
          </Link>

          <nav className="flex items-center gap-3 sm:gap-5" aria-label="Primary navigation">
            <Link
              to="/"
              className="hidden text-sm font-semibold text-slate-600 transition hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 sm:block"
            >
              New Analysis
            </Link>
            <a
              href="https://github.com/enstso/article50-autodisclosure"
              target="_blank"
              rel="noreferrer"
              className="hidden text-sm font-semibold text-slate-600 transition hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 md:block"
            >
              GitHub
            </a>
            <div className="hidden h-5 w-px bg-slate-200 sm:block" />
            {activeMode === "DEMO" ? (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1 text-[11px] font-bold text-violet-700">
                <span className="h-1.5 w-1.5 rounded-full bg-violet-500" />
                Mock model enabled
              </span>
            ) : (
              <span className="hidden items-center gap-1.5 rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-[11px] font-bold text-sky-700 lg:inline-flex">
                <span className="h-1.5 w-1.5 rounded-full bg-sky-500" />
                Amazon Bedrock configured
              </span>
            )}
            <ApiConnectionStatus status={apiStatus} />
          </nav>
        </div>
      </header>

      {children}

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-5 py-7 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <p>Built for AWS Agents for Humans Hackathon</p>
          <p>Strands Agents SDK · Amazon Bedrock · Static analysis only</p>
        </div>
      </footer>
    </div>
  );
}
