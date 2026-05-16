import type { ReactNode } from "react";
import { useLogout, useMe } from "../lib/hooks";

export function AppShell({ children }: { children: ReactNode }) {
  const { data: user } = useMe();
  const logout = useLogout();

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between">
          <h1 className="text-base font-semibold text-slate-900">repo-manage</h1>
          <div className="flex items-center gap-3">
            {user && (
              <span className="text-sm text-slate-500">
                {user.display_name || user.email}
              </span>
            )}
            <button
              onClick={() => logout.mutate()}
              disabled={logout.isPending}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition disabled:opacity-50"
            >
              {logout.isPending ? "Logging out…" : "Log out"}
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-6 py-8">{children}</main>
    </div>
  );
}
