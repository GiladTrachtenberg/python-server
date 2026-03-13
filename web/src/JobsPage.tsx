import { useCallback, useEffect, useState } from "react";
import {
  type JobData,
  type PaginationMeta,
  createJob,
  listJobs,
} from "./api";

interface Props {
  token: string;
  onSelectJob: (jobId: string) => void;
  onLogout: () => void;
}

export function JobsPage({ token, onSelectJob, onLogout }: Props) {
  const [jobs, setJobs] = useState<JobData[]>([]);
  const [meta, setMeta] = useState<PaginationMeta | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (p: number) => {
      setLoading(true);
      setError(null);
      try {
        const result = await listJobs(token, p);
        setJobs(result.data);
        setMeta(result.meta);
        setPage(p);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load jobs");
      } finally {
        setLoading(false);
      }
    },
    [token],
  );

  useEffect(() => {
    void load(1);
  }, [load]);

  async function handleCreate() {
    setCreating(true);
    setError(null);
    try {
      await createJob(token);
      await load(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create job");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="page">
      <header className="top-bar">
        <h1>Jobs</h1>
        <div className="top-bar-actions">
          <button
            type="button"
            className="btn-primary"
            onClick={handleCreate}
            disabled={creating}
          >
            {creating ? "Creating..." : "New Job"}
          </button>
          <button type="button" className="btn-secondary" onClick={onLogout}>
            Logout
          </button>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      <table className="jobs-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Status</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr
              key={job.id}
              className="clickable"
              onClick={() => onSelectJob(job.id)}
            >
              <td className="mono">{job.id.slice(0, 8)}</td>
              <td>
                <span className={`badge badge-${job.status}`}>
                  {job.status}
                </span>
              </td>
              <td>{new Date(job.created_at).toLocaleString()}</td>
            </tr>
          ))}
          {jobs.length === 0 && !loading && (
            <tr>
              <td colSpan={3} className="empty">
                No jobs yet
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {meta && meta.total_pages > 1 && (
        <div className="pagination">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => void load(page - 1)}
          >
            Prev
          </button>
          <span>
            {page} / {meta.total_pages}
          </span>
          <button
            type="button"
            disabled={page >= meta.total_pages}
            onClick={() => void load(page + 1)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
