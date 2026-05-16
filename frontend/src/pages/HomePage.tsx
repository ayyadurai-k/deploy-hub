import { useState } from "react";
import axios from "axios";
import {
  oauthStartUrl,
  useMe,
  useProjects,
  useRepositories,
  useSyncRepositories,
} from "../lib/hooks";
import type { Project, Repository } from "../lib/types";

export function HomePage() {
  return (
    <div className="space-y-10">
      <UserCard />
      <ReposSection />
      <ProjectsSection />
    </div>
  );
}

// ---------- User ----------

function UserCard() {
  const { data: user, isLoading, error } = useMe();
  if (isLoading) return <Section title="You"><p className="text-sm text-slate-500">Loading…</p></Section>;
  if (error || !user) return <Section title="You"><p className="text-sm text-red-600">Failed to load profile.</p></Section>;

  return (
    <Section title="You">
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-baseline justify-between">
          <div>
            <div className="text-lg font-medium text-slate-900">
              {user.display_name || user.email}
            </div>
            <div className="text-sm text-slate-500">{user.email}</div>
          </div>
          <div className="text-xs text-slate-400">
            Member since {new Date(user.date_joined).toLocaleDateString()}
          </div>
        </div>
        <div className="mt-4 flex gap-2">
          <ProviderBadge label="Google" linked={user.has_google} />
          <ProviderBadge label="GitHub" linked={user.has_github} />
        </div>
      </div>
    </Section>
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
      <span className={linked ? "h-1.5 w-1.5 rounded-full bg-emerald-500" : "h-1.5 w-1.5 rounded-full bg-slate-300"} />
      {label} {linked ? "linked" : "not linked"}
    </span>
  );
}

// ---------- Repositories ----------

function ReposSection() {
  const repos = useRepositories();
  const sync = useSyncRepositories();
  const { data: user } = useMe();

  // 409 means no GitHub linked yet — show Connect CTA instead of an error.
  if (repos.error && axios.isAxiosError(repos.error) && repos.error.response?.status === 409) {
    return (
      <Section title="Repositories">
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-center">
          <p className="text-sm text-slate-600 mb-4">
            Connect your GitHub account to see your repositories.
          </p>
          <a
            href={oauthStartUrl("github")}
            className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 transition"
          >
            Connect GitHub
          </a>
        </div>
      </Section>
    );
  }

  return (
    <Section
      title="Repositories"
      right={
        user?.has_github && (
          <button
            onClick={() => sync.mutate()}
            disabled={sync.isPending}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition disabled:opacity-50"
          >
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
        <Banner kind="error">Failed to load repositories. {asMessage(repos.error)}</Banner>
      ) : repos.data && repos.data.results.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
          No repositories yet — click <strong>Sync</strong> above.
        </div>
      ) : (
        <ul className="divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white">
          {repos.data?.results.map((r) => <RepoRow key={r.id} repo={r} />)}
        </ul>
      )}
    </Section>
  );
}

function RepoRow({ repo }: { repo: Repository }) {
  return (
    <li className="flex items-center justify-between gap-3 px-4 py-3">
      <div className="min-w-0">
        <a
          href={repo.html_url}
          target="_blank"
          rel="noreferrer noopener"
          className="font-medium text-slate-900 hover:text-slate-700"
        >
          {repo.full_name}
        </a>
        {repo.description && (
          <p className="text-sm text-slate-500 truncate max-w-prose">{repo.description}</p>
        )}
        <div className="mt-1 flex items-center gap-3 text-xs text-slate-500">
          {repo.private ? (
            <span className="inline-flex items-center rounded bg-amber-50 px-1.5 py-0.5 text-amber-700 ring-1 ring-amber-200">
              Private
            </span>
          ) : (
            <span className="inline-flex items-center rounded bg-slate-100 px-1.5 py-0.5 text-slate-600 ring-1 ring-slate-200">
              Public
            </span>
          )}
          {repo.default_branch && <span>branch: {repo.default_branch}</span>}
          {repo.github_pushed_at && (
            <span>pushed {new Date(repo.github_pushed_at).toLocaleDateString()}</span>
          )}
        </div>
      </div>
    </li>
  );
}

// ---------- Projects ----------

function ProjectsSection() {
  const projects = useProjects();
  const repos = useRepositories();

  const repoById = new Map<number, Repository>();
  repos.data?.results.forEach((r) => repoById.set(r.id, r));

  return (
    <Section title="Projects">
      {projects.isLoading ? (
        <p className="text-sm text-slate-500">Loading projects…</p>
      ) : projects.error ? (
        <Banner kind="error">Failed to load projects.</Banner>
      ) : projects.data && projects.data.results.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
          No projects yet. Create one via the Django admin.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Repository</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {projects.data?.results.map((p) => (
                <ProjectRow
                  key={p.id}
                  project={p}
                  repo={p.repository ? repoById.get(p.repository) : undefined}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function ProjectRow({ project, repo }: { project: Project; repo: Repository | undefined }) {
  const [toast, setToast] = useState<string | null>(null);

  const handleDeploy = () => {
    setToast("Deployment is not yet supported — coming soon");
    setTimeout(() => setToast(null), 2500);
  };

  return (
    <tr className="hover:bg-slate-50">
      <td className="px-4 py-3 font-medium text-slate-900">{project.name}</td>
      <td className="px-4 py-3 text-slate-600">
        {repo ? repo.full_name : <span className="text-slate-400">—</span>}
      </td>
      <td className="px-4 py-3">
        <span className="inline-flex items-center rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
          {project.status}
        </span>
      </td>
      <td className="px-4 py-3 text-right">
        <div className="inline-flex flex-col items-end gap-1">
          <button
            onClick={handleDeploy}
            className="rounded-md bg-purple-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-purple-700 transition"
          >
            Deploy to K8S
          </button>
          {toast && (
            <span className="text-xs text-purple-700">{toast}</span>
          )}
        </div>
      </td>
    </tr>
  );
}

// ---------- Helpers ----------

function Section({
  title,
  right,
  children,
}: {
  title: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          {title}
        </h2>
        {right}
      </div>
      {children}
    </section>
  );
}

function Banner({ kind, children }: { kind: "success" | "error"; children: React.ReactNode }) {
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
