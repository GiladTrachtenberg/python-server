import { useEffect, useRef, useState } from "react";
import { type JobData, cancelJob, getJob, sseUrl } from "./api";

interface Props {
  token: string;
  jobId: string;
  onBack: () => void;
  onLogout: () => void;
}

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

export function JobDetailPage({ token, jobId, onBack, onLogout }: Props) {
  const [job, setJob] = useState<JobData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const data = await getJob(token, jobId);
        if (cancelled) return;
        setJob(data);

        if (TERMINAL.has(data.status)) return;

        const es = new EventSource(sseUrl(jobId, token));
        esRef.current = es;

        es.addEventListener("status", (e: MessageEvent<string>) => {
          const parsed = JSON.parse(e.data) as { status: string };
          setJob((prev) =>
            prev ? { ...prev, status: parsed.status } : prev,
          );

          if (TERMINAL.has(parsed.status)) {
            es.close();
            void refetch();
          }
        });

        es.onerror = () => {
          es.close();
        };
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load job");
        }
      }
    }

    async function refetch() {
      try {
        const data = await getJob(token, jobId);
        if (!cancelled) setJob(data);
      } catch {
        /* best effort */
      }
    }

    void init();

    return () => {
      cancelled = true;
      esRef.current?.close();
    };
  }, [token, jobId]);

  async function handleCancel() {
    setCancelling(true);
    setError(null);
    try {
      const updated = await cancelJob(token, jobId);
      setJob(updated);
      esRef.current?.close();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cancel failed");
    } finally {
      setCancelling(false);
    }
  }

  const canCancel =
    job && (job.status === "pending" || job.status === "processing");

  return (
    <div className="page">
      <header className="top-bar">
        <button type="button" className="btn-secondary" onClick={onBack}>
          Back
        </button>
        <h1>Job Detail</h1>
        <button type="button" className="btn-secondary" onClick={onLogout}>
          Logout
        </button>
      </header>

      {error && <p className="error">{error}</p>}

      {job && (
        <div className="detail-card">
          <dl>
            <dt>ID</dt>
            <dd className="mono">{job.id}</dd>

            <dt>Status</dt>
            <dd>
              <span className={`badge badge-${job.status}`}>{job.status}</span>
            </dd>

            <dt>Created</dt>
            <dd>{new Date(job.created_at).toLocaleString()}</dd>

            <dt>Updated</dt>
            <dd>{new Date(job.updated_at).toLocaleString()}</dd>

            {job.error_message && (
              <>
                <dt>Error</dt>
                <dd className="error">{job.error_message}</dd>
              </>
            )}
          </dl>

          <div className="detail-actions">
            {canCancel && (
              <button
                type="button"
                className="btn-danger"
                disabled={cancelling}
                onClick={handleCancel}
              >
                {cancelling ? "Cancelling..." : "Cancel Job"}
              </button>
            )}

            {job.download_url && (
              <a
                href={job.download_url}
                className="btn-primary"
                target="_blank"
                rel="noopener noreferrer"
              >
                Download File
              </a>
            )}
          </div>
        </div>
      )}

      {!job && !error && <p className="loading">Loading...</p>}
    </div>
  );
}
