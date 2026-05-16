import { Navigate, useSearchParams } from "react-router-dom";
import { oauthStartUrl, useAccessToken } from "../lib/hooks";

export function LoginPage() {
  const token = useAccessToken();
  const [params] = useSearchParams();
  const errorMessage = params.get("message");

  if (token) return <Navigate to="/" replace />;

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-slate-900">repo-manage</h1>
          <p className="text-sm text-slate-500 mt-1">
            Sign in to browse your GitHub repos and manage deploy projects.
          </p>
        </div>

        {errorMessage && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {errorMessage}
          </div>
        )}

        <div className="space-y-3">
          <a
            href={oauthStartUrl("google")}
            className="flex items-center justify-center gap-3 w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition"
          >
            <GoogleIcon className="h-5 w-5" />
            Sign in with Google
          </a>
          <a
            href={oauthStartUrl("github")}
            className="flex items-center justify-center gap-3 w-full rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-800 transition"
          >
            <GitHubIcon className="h-5 w-5" />
            Sign in with GitHub
          </a>
        </div>

        <p className="mt-8 text-xs text-slate-400 text-center">
          Google = identity only. GitHub gives access to your repos.
        </p>
      </div>
    </div>
  );
}

function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path
        fill="#4285F4"
        d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.44c-.28 1.48-1.12 2.74-2.39 3.58v2.97h3.86c2.26-2.09 3.58-5.17 3.58-8.79z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.95-1.08 7.94-2.94l-3.86-2.97c-1.07.72-2.43 1.16-4.08 1.16-3.13 0-5.79-2.11-6.74-4.96H1.27v3.07A11.99 11.99 0 0012 24z"
      />
      <path
        fill="#FBBC05"
        d="M5.26 14.29A7.2 7.2 0 014.87 12c0-.79.14-1.56.39-2.29V6.64H1.27a12 12 0 000 10.72l3.99-3.07z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0A12 12 0 001.27 6.64l3.99 3.07C6.21 6.86 8.87 4.75 12 4.75z"
      />
    </svg>
  );
}

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" fill="currentColor">
      <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.1.79-.25.79-.56v-2.16c-3.2.7-3.88-1.36-3.88-1.36-.52-1.34-1.27-1.69-1.27-1.69-1.04-.72.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.03 1.76 2.7 1.25 3.36.95.1-.74.4-1.25.73-1.54-2.55-.29-5.23-1.27-5.23-5.66 0-1.25.45-2.27 1.18-3.07-.12-.29-.51-1.46.11-3.04 0 0 .96-.31 3.15 1.17.91-.26 1.89-.39 2.86-.39.97 0 1.95.13 2.86.39 2.18-1.48 3.14-1.17 3.14-1.17.62 1.58.23 2.75.11 3.04.73.8 1.18 1.82 1.18 3.07 0 4.4-2.69 5.37-5.25 5.65.41.35.78 1.05.78 2.13v3.16c0 .31.21.67.8.55C20.21 21.38 23.5 17.08 23.5 12c0-6.35-5.15-11.5-11.5-11.5z" />
    </svg>
  );
}
