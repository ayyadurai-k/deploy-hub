import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { setAccessToken } from "../lib/authStore";

// Backend redirects here with one of:
//   #access=<jwt>&intent=login        (login)
//   #linked=<provider>&intent=link    (link)
//   #error=<code>&message=<...>       (failure)
export function AuthComplete() {
  const navigate = useNavigate();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    const hash = window.location.hash.replace(/^#/, "");
    const params = new URLSearchParams(hash);

    // Clear the fragment so it doesn't linger in history / get pasted.
    window.history.replaceState(null, "", window.location.pathname);

    const error = params.get("error");
    if (error) {
      const message = params.get("message") ?? error;
      setErrorMsg(message);
      const t = setTimeout(() => {
        navigate(`/login?message=${encodeURIComponent(message)}`, { replace: true });
      }, 1200);
      return () => clearTimeout(t);
    }

    const access = params.get("access");
    if (access) {
      setAccessToken(access);
      navigate("/", { replace: true });
      return;
    }

    // Link flow: no access token, just a linked=<provider> echo. Go home.
    if (params.get("linked")) {
      navigate("/", { replace: true });
      return;
    }

    // Nothing useful in the fragment.
    navigate("/login", { replace: true });
  }, [navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="text-sm text-slate-500">
        {errorMsg ? `Authentication failed: ${errorMsg}` : "Completing sign-in…"}
      </div>
    </div>
  );
}
