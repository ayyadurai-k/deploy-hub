import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { AuthGuard } from "./components/AuthGuard";
import { AuthComplete } from "./pages/AuthComplete";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/complete" element={<AuthComplete />} />
      <Route
        path="/"
        element={
          <AuthGuard>
            <AppShell>
              <HomePage />
            </AppShell>
          </AuthGuard>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
