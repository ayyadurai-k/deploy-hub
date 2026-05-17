import type { ReactNode } from "react";
import { useLogout, useMe } from "../lib/hooks";
import { Brand } from "./Brand";

export function AppShell({ children }: { children: ReactNode }) {
  const { data: user } = useMe();
  const logout = useLogout();

  const initials = (user?.display_name || user?.email || "?")
    .split(/[\s.@]/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase())
    .join("");

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/85 backdrop-blur">
        <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between">
          <a href="/" className="inline-flex items-center" aria-label="Deploy Hub home">
            <Brand size={26} textClassName="text-base" />
          </a>
          <div className="flex items-center gap-3">
            {user && (
              <div className="hidden sm:flex items-center gap-2 rounded-full bg-slate-100 pl-1 pr-3 py-1 ring-1 ring-slate-200">
                <span className="grid place-items-center h-6 w-6 rounded-full bg-violet-600 text-white text-[10px] font-semibold">
                  {initials || "U"}
                </span>
                <span className="text-xs font-medium text-slate-700 max-w-[12rem] truncate">
                  {user.display_name || user.email}
                </span>
              </div>
            )}
            <button
              onClick={() => logout.mutate()}
              disabled={logout.isPending}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition disabled:opacity-50"
            >
              {logout.isPending ? "Logging out…" : "Log out"}
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-6 py-10">{children}</main>
      <footer className="max-w-5xl mx-auto px-6 py-8 text-center text-xs text-slate-400">
        Deploy Hub · <a className="hover:text-slate-600" href="https://github.com/ayyadurai-k" target="_blank" rel="noreferrer">github</a>
      </footer>
    </div>
  );
}
