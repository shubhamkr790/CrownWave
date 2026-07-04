import { useEffect, useState } from 'react';
import { api } from '../api';

export default function DashboardPage() {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getOverview()
      .then(res => setOverview(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="empty-state"><p>Loading...</p></div>;
  if (!overview) return <div className="empty-state"><p>Failed to load metrics</p></div>;

  const { jobs, workers, queues, dlq } = overview;

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1>Overview</h1>
        <p>System health and throughput</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Total jobs</div>
          <div className="stat-value">{jobs.total.toLocaleString()}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Success rate</div>
          <div className="stat-value">{jobs.success_rate}%</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Active workers</div>
          <div className="stat-value">{workers.by_status?.online || 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Queues</div>
          <div className="stat-value">{queues.total}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Unresolved DLQ</div>
          <div className="stat-value">{dlq.unresolved}</div>
          {dlq.unresolved > 0 && (
            <div className="stat-detail" style={{ color: 'var(--red-500)' }}>
              Needs attention
            </div>
          )}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
        <div className="card-header">
          <span className="card-title">Jobs by status</span>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Status</th>
              <th style={{ textAlign: 'right' }}>Count</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(jobs.by_status || {}).map(([status, count]) => (
              <tr key={status}>
                <td>
                  <span className={`badge badge-${status}`}>{status}</span>
                </td>
                <td style={{ textAlign: 'right' }}>{count.toLocaleString()}</td>
              </tr>
            ))}
            {Object.keys(jobs.by_status || {}).length === 0 && (
              <tr>
                <td colSpan={2} style={{ textAlign: 'center', color: 'var(--text-tertiary)' }}>
                  No jobs yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">Workers by status</span>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Status</th>
              <th style={{ textAlign: 'right' }}>Count</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(workers.by_status || {}).map(([status, count]) => (
              <tr key={status}>
                <td>
                  <span className={`badge badge-${status}`}>{status}</span>
                </td>
                <td style={{ textAlign: 'right' }}>{count}</td>
              </tr>
            ))}
            {Object.keys(workers.by_status || {}).length === 0 && (
              <tr>
                <td colSpan={2} style={{ textAlign: 'center', color: 'var(--text-tertiary)' }}>
                  No workers registered
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
