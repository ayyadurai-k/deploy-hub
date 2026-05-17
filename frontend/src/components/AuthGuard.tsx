import { type ReactNode, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../lib/api";
import { setAccessToken } from "../lib/authStore";
import { useAccessToken } from "../lib/hooks";

// On a browser refresh, the in-memory access token is gone (by design — see
// OAUTH_FLOW.md §10), but the httpOnly refresh cookie is still in the browser.
// Without this guard attempting a /auth/refresh before redirecting, every page
// reload would log the user out — a bug, not the intended behaviour.
export function AuthGuard({ children }: { children: ReactNode }) {
  const token = useAccessToken();
  const [bootstrapping, setBootstrapping] = useState(!token);

  useEffect(() => {
    if (token) {
      // Already authenticated (e.g., we just came from AuthComplete) — nothing
      // to bootstrap; render straight through.
      setBootstrapping(false);
      return;
    }

    let cancelled = false;
    api
      .post<{ access: string }>("/auth/refresh", {})
      .then((res) => {
        if (cancelled) return;
        setAccessToken(res.data.access);
      })
      .catch(() => {
        // No valid refresh cookie — first visit, cookie expired, or session
        // was blacklisted (logout / reuse-detection). Falling through; the
        // !token check below will route to /login.
      })
      .finally(() => {
        if (!cancelled) setBootstrapping(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (bootstrapping) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-sm text-slate-500">Loading…</div>
      </div>
    );
  }
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
