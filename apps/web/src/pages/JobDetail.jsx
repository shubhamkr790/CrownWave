import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api';

export default function JobDetailPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getJob(jobId)
      .then(res => setJob(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [jobId]);

  function formatTime(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString();
  }

  if (loading) return <div className="empty-state"><p>Loading...</p></div>;
  if (!job) return <div className="empty-state"><p>Job not found</p></div>;

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1>{job.name}</h1>
        <p className="mono">{job.id}</p>
      </div>

      <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
        <div className="card-header">
          <span className="card-title">Details</span>
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            {(job.status === 'failed' || job.status === 'dead') && (
              <button className="btn btn-sm" onClick={() => api.retryJob(job.id).then(() => window.location.reload())}>
                Retry
              </button>
            )}
            {(job.status === 'queued' || job.status === 'scheduled') && (
              <button className="btn btn-sm btn-danger" onClick={() => api.cancelJob(job.id).then(() => navigate('/jobs'))}>
                Cancel
              </button>
            )}
          </div>
        </div>
        <div className="detail-grid">
          <span className="detail-label">Status</span>
          <span><span className={`badge badge-${job.status}`}>{job.status}</span></span>

          <span className="detail-label">Priority</span>
          <span className="detail-value">{job.priority}</span>

          <span className="detail-label">Attempts</span>
          <span className="detail-value">{job.attempt_count} / {job.max_attempts}</span>

          <span className="detail-label">Queue</span>
          <span className="detail-value mono">{job.queue_id.substring(0, 8)}</span>

          <span className="detail-label">Created</span>
          <span className="detail-value">{formatTime(job.created_at)}</span>

          <span className="detail-label">Claimed</span>
          <span className="detail-value">{formatTime(job.claimed_at)}</span>

          <span className="detail-label">Started</span>
          <span className="detail-value">{formatTime(job.started_at)}</span>

          <span className="detail-label">Completed</span>
          <span className="detail-value">{formatTime(job.completed_at)}</span>

          {job.idempotency_key && (
            <>
              <span className="detail-label">Idempotency key</span>
              <span className="detail-value mono">{job.idempotency_key}</span>
            </>
          )}

          {job.last_error && (
            <>
              <span className="detail-label">Last error</span>
              <span className="detail-value" style={{ color: 'var(--red-600)' }}>{job.last_error}</span>
            </>
          )}
        </div>
      </div>

      {job.executions && job.executions.length > 0 && (
        <div className="card">
          <div className="card-header">
            <span className="card-title">Execution history</span>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Attempt</th>
                <th>Status</th>
                <th>Started</th>
                <th>Duration</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {job.executions.map(e => (
                <tr key={e.id}>
                  <td>#{e.attempt_number}</td>
                  <td>
                    <span className={`badge badge-${e.status}`}>{e.status}</span>
                  </td>
                  <td className="timestamp">{formatTime(e.started_at)}</td>
                  <td>{e.duration_ms != null ? `${e.duration_ms}ms` : '—'}</td>
                  <td style={{ color: 'var(--red-600)', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {e.error_message || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
