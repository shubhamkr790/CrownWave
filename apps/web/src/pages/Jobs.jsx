import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';

export default function JobsPage() {
  const [jobs, setJobs] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadJobs();
  }, [page, statusFilter]);

  async function loadJobs() {
    setLoading(true);
    try {
      const params = { page, per_page: 50 };
      if (statusFilter) params.status = statusFilter;
      const res = await api.listJobs(params);
      setJobs(res.data || []);
      setPagination(res.pagination);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  const statuses = ['', 'queued', 'running', 'completed', 'failed', 'retry_scheduled', 'dead', 'cancelled'];

  function formatTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleString('en-US', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  }

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1>Jobs</h1>
        <p>Browse and manage all jobs across queues</p>
      </div>

      <div style={{ marginBottom: 'var(--space-4)', display: 'flex', gap: 'var(--space-2)' }}>
        <select
          className="form-input"
          style={{ width: 'auto' }}
          value={statusFilter}
          onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
        >
          <option value="">All statuses</option>
          {statuses.filter(Boolean).map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      <div className="card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Priority</th>
              <th>Attempts</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map(j => (
              <tr key={j.id}>
                <td>
                  <Link to={`/jobs/${j.id}`} style={{ fontWeight: 500 }}>{j.name}</Link>
                  <div className="mono" style={{ color: 'var(--text-tertiary)', marginTop: '2px' }}>
                    {j.id.substring(0, 8)}
                  </div>
                </td>
                <td>
                  <span className={`badge badge-${j.status}`}>{j.status}</span>
                </td>
                <td>{j.priority}</td>
                <td>{j.attempt_count}/{j.max_attempts}</td>
                <td className="timestamp">{formatTime(j.created_at)}</td>
                <td>
                  {(j.status === 'failed' || j.status === 'dead') && (
                    <button className="btn btn-sm" onClick={() => api.retryJob(j.id).then(loadJobs)}>
                      Retry
                    </button>
                  )}
                  {(j.status === 'queued' || j.status === 'scheduled') && (
                    <button className="btn btn-sm btn-danger" onClick={() => api.cancelJob(j.id).then(loadJobs)}>
                      Cancel
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {jobs.length === 0 && !loading && (
              <tr>
                <td colSpan={6} className="empty-state">No jobs found</td>
              </tr>
            )}
          </tbody>
        </table>

        {pagination && pagination.total_pages > 1 && (
          <div className="pagination">
            <span>
              Page {pagination.page} of {pagination.total_pages}
              {' · '}{pagination.total} total
            </span>
            <div className="pagination-buttons">
              <button className="btn btn-sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
                Previous
              </button>
              <button className="btn btn-sm" disabled={page >= pagination.total_pages} onClick={() => setPage(p => p + 1)}>
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
