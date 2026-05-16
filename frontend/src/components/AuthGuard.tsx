import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAccessToken } from "../lib/hooks";

export function AuthGuard({ children }: { children: ReactNode }) {
  const token = useAccessToken();
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
