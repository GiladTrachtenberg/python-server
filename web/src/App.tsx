import { useCallback, useEffect, useState } from "react";
import { AuthPage } from "./AuthPage";
import { JobDetailPage } from "./JobDetailPage";
import { JobsPage } from "./JobsPage";

type View = "auth" | "jobs" | "detail";

const TOKEN_KEY = "access_token";
const REFRESH_KEY = "refresh_token";

export function App() {
  const [view, setView] = useState<View>("auth");
  const [token, setToken] = useState<string | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (stored) {
      setToken(stored);
      setView("jobs");
    }
  }, []);

  const handleLogin = useCallback((accessToken: string, refreshToken: string) => {
    localStorage.setItem(TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_KEY, refreshToken);
    setToken(accessToken);
    setView("jobs");
  }, []);

  const handleLogout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    setToken(null);
    setSelectedJobId(null);
    setView("auth");
  }, []);

  const handleSelectJob = useCallback((jobId: string) => {
    setSelectedJobId(jobId);
    setView("detail");
  }, []);

  const handleBack = useCallback(() => {
    setSelectedJobId(null);
    setView("jobs");
  }, []);

  if (view === "auth" || !token) {
    return <AuthPage onLogin={handleLogin} />;
  }

  if (view === "detail" && selectedJobId) {
    return (
      <JobDetailPage
        token={token}
        jobId={selectedJobId}
        onBack={handleBack}
        onLogout={handleLogout}
      />
    );
  }

  return (
    <JobsPage
      token={token}
      onSelectJob={handleSelectJob}
      onLogout={handleLogout}
    />
  );
}
