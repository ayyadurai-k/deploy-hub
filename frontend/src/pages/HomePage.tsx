import { useState } from "react";
import axios from "axios";
import {
  useMe,
  useRepositories,
  useSyncRepositories,
} from "../lib/hooks";
import type { Repository } from "../lib/types";

export function HomePage() {
  return (
    <div className="space-y-10">
      <WelcomeHeader />
      <StatsStrip />
      <ReposSection />
    </div>
  );
}

// ---------- Welcome header ----------

function WelcomeHeader() {
  const { data: user, isLoading, error } = useMe();

  if (isLoading || error || !user) {
    return (
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Welcome
        </h1>
        <p className="mt-1 text-sm text-slate-500">Loading your dashboard…</p>
      </header>
    );
  }

  const firstName = (user.display_name || user.email).split(/[\s@]/)[0];

  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Hey, {firstName}.
        </h1>
        <p className="mt-1 text-sm text-slate-500">{user.email}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <ProviderBadge label="Google" linked={user.has_google} />
        <ProviderBadge label="GitHub" linked={user.has_github} />
      </div>
    </header>
  );
}

function ProviderBadge({ label, linked }: { label: string; linked: boolean }) {
  return (
    <span
      className={
        linked
          ? "inline-flex items-center gap-1.5 rounded-full bg-emerald-50 text-emerald-700 px-2.5 py-0.5 text-xs font-medium ring-1 ring-emerald-200"
          : "inline-flex items-center gap-1.5 rounded-full bg-slate-100 text-slate-500 px-2.5 py-0.5 text-xs font-medium ring-1 ring-slate-200"
      }
    >
      <span
        className={
          linked
            ? "h-1.5 w-1.5 rounded-full bg-emerald-500"
            : "h-1.5 w-1.5 rounded-full bg-slate-300"
        }
      />
      {label} {linked ? "linked" : "not linked"}
    </span>
  );
}

// ---------- Stats strip ----------

function StatsStrip() {
  const repos = useRepositories();

  const repoCount = repos.data?.count;
  const has409 =
    repos.isError &&
    axios.isAxiosError(repos.error) &&
    repos.error.response?.status === 409;

  const repoText = has409 ? "—" : repoCount ?? "…";

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <StatCard label="Repositories" value={repoText} hint="Synced from GitHub" />
      <StatCard label="Deployments" value="0" hint="Coming soon" tone="muted" />
    </div>
  );
}

function StatCard({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: number | string;
  hint?: string;
  tone?: "default" | "muted";
}) {
  return (
    <div
      className={
        "rounded-xl border bg-white p-4 " +
        (tone === "muted" ? "border-slate-200/70 opacity-80" : "border-slate-200")
      }
    >
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold tabular-nums tracking-tight text-slate-900">
        {value}
      </div>
      {hint && <div className="mt-0.5 text-xs text-slate-400">{hint}</div>}
    </div>
  );
}

// ---------- Repositories ----------

function ReposSection() {
  const repos = useRepositories();
  const sync = useSyncRepositories();
  const { data: user } = useMe();

  // 409 means the signed-in user authenticated via Google only. Repos come
  // from GitHub, so the section is informational — log out and sign back in
  // via GitHub to populate it.
  if (
    repos.error &&
    axios.isAxiosError(repos.error) &&
    repos.error.response?.status === 409
  ) {
    return (
      <Section title="Repositories">
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-7 text-center">
          <p className="text-sm text-slate-700">
            Sign in with <span className="font-medium text-slate-900">GitHub</span> to see your repositories.
          </p>
          <p className="mt-1 text-xs text-slate-400">
            Use <span className="font-medium">Log out</span> above, then choose Sign in with GitHub.
          </p>
        </div>
      </Section>
    );
  }

  return (
    <Section
      title="Repositories"
      hint={repos.data?.count ? `${repos.data.count} synced` : undefined}
      right={
        user?.has_github && (
          <button
            onClick={() => sync.mutate()}
            disabled={sync.isPending}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 disabled:opacity-50"
          >
            <SyncIcon spinning={sync.isPending} />
            {sync.isPending ? "Syncing…" : "Sync"}
          </button>
        )
      }
    >
      {sync.error ? (
        <Banner kind="error">Sync failed. {asMessage(sync.error)}</Banner>
      ) : sync.data ? (
        <Banner kind="success">
          Synced {sync.data.synced} repositor{sync.data.synced === 1 ? "y" : "ies"}.
        </Banner>
      ) : null}

      {repos.isLoading ? (
        <p className="text-sm text-slate-500">Loading repositories…</p>
      ) : repos.error ? (
        <Banner kind="error">
          Failed to load repositories. {asMessage(repos.error)}
        </Banner>
      ) : repos.data && repos.data.results.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-7 text-center text-sm text-slate-500">
          No repositories yet — click <strong>Sync</strong> above.
        </div>
      ) : (
        <ul className="divide-y divide-slate-200 overflow-hidden rounded-xl border border-slate-200 bg-white">
          {repos.data?.results.map((r) => (
            <RepoRow key={r.id} repo={r} />
          ))}
        </ul>
      )}
    </Section>
  );
}

function RepoRow({ repo }: { repo: Repository }) {
  const [toast, setToast] = useState<string | null>(null);

  const handleDeploy = () => {
    setToast("Deployment coming soon");
    setTimeout(() => setToast(null), 2500);
  };

  return (
    <li className="flex items-center justify-between gap-4 px-4 py-3 transition hover:bg-slate-50/70">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <a
            href={repo.html_url}
            target="_blank"
            rel="noreferrer noopener"
            className="truncate font-medium text-slate-900 hover:text-violet-700"
          >
            {repo.full_name}
          </a>
          {repo.private ? (
            <span className="inline-flex shrink-0 items-center rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-700 ring-1 ring-amber-200">
              Private
            </span>
          ) : (
            <span className="inline-flex shrink-0 items-center rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600 ring-1 ring-slate-200">
              Public
            </span>
          )}
        </div>
        {repo.description && (
          <p className="mt-0.5 max-w-prose truncate text-sm text-slate-500">
            {repo.description}
          </p>
        )}
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-slate-400">
          {repo.default_branch && <span>branch · {repo.default_branch}</span>}
          {repo.github_pushed_at && (
            <span>pushed {timeAgo(repo.github_pushed_at)}</span>
          )}
        </div>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1">
        <button
          onClick={handleDeploy}
          className="inline-flex items-center gap-1.5 rounded-md bg-violet-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-violet-700"
        >
          <RocketIcon />
          Deploy to K8S
        </button>
        {toast && <span className="text-xs text-violet-700">{toast}</span>}
      </div>
    </li>
  );
}

// ---------- Helpers ----------

function Section({
  title,
  hint,
  right,
  children,
}: {
  title: string;
  hint?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-baseline gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            {title}
          </h2>
          {hint && <span className="text-xs text-slate-400">· {hint}</span>}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

function Banner({
  kind,
  children,
}: {
  kind: "success" | "error";
  children: React.ReactNode;
}) {
  const cls =
    kind === "success"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : "border-red-200 bg-red-50 text-red-700";
  return (
    <div className={`mb-3 rounded-lg border px-3 py-2 text-sm ${cls}`}>{children}</div>
  );
}

function asMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data;
    if (data && typeof data === "object" && "error" in data) {
      const e = (data as { error?: { message?: string } }).error;
      if (e?.message) return e.message;
    }
    return err.message;
  }
  return String(err);
}

function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  const days = Math.floor(diff / 86_400_000);
  if (days < 1) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.floor(months / 12)}y ago`;
}

function SyncIcon({ spinning }: { spinning: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={`h-3.5 w-3.5 ${spinning ? "animate-spin" : ""}`}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M21 12a9 9 0 0 1-15.36 6.36L3 17" />
      <path d="M3 12a9 9 0 0 1 15.36-6.36L21 7" />
      <path d="M21 3v4h-4" />
      <path d="M3 21v-4h4" />
    </svg>
  );
}

function RocketIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-3.5 w-3.5"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z" />
      <path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z" />
      <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0" />
      <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5" />
    </svg>
  );
}
