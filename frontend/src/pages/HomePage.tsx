import { FormEvent, useEffect, useState } from "react";

import { getHealth } from "../api/health";
import { ApiConnectionStatus } from "../components/ApiConnectionStatus";
import type { ApiStatus } from "../types/api";

export function HomePage() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [showComingSoon, setShowComingSoon] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    getHealth(controller.signal)
      .then((health) => setApiStatus(health.status === "ok" ? "connected" : "offline"))
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          setApiStatus("offline");
        }
      });

    return () => controller.abort();
  }, []);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setShowComingSoon(true);
  }

  return (
    <div className="min-h-screen bg-canvas">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-ink text-sm font-bold text-white">
              A50
            </div>
            <span className="text-sm font-semibold tracking-tight text-ink">
              Article 50 AutoDisclosure
            </span>
          </div>
          <ApiConnectionStatus status={apiStatus} />
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-24 sm:py-32">
        <div className="mb-8 inline-flex rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600">
          EU AI Act transparency checks
        </div>
        <h1 className="max-w-2xl text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
          Article 50 AutoDisclosure
        </h1>
        <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-600">
          Analyze AI applications for missing transparency disclosures before release.
        </p>

        <form
          className="mt-12 rounded-xl border border-slate-200 bg-white p-6 shadow-panel sm:p-8"
          onSubmit={handleSubmit}
        >
          <label htmlFor="repository-url" className="block text-sm font-medium text-slate-800">
            GitHub repository URL
          </label>
          <p className="mt-1 text-sm text-slate-500">
            Enter a public repository containing an AI-powered application.
          </p>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row">
            <input
              id="repository-url"
              name="repository-url"
              type="url"
              placeholder="https://github.com/organization/repository"
              className="min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
            />
            <button
              type="submit"
              className="rounded-md bg-ink px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
            >
              Analyze Repository
            </button>
          </div>
          {showComingSoon && (
            <p className="mt-4 text-sm text-slate-600" role="status">
              Repository analysis coming next.
            </p>
          )}
        </form>
      </main>
    </div>
  );
}

