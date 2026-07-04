import { useEffect, useState } from 'react';
import { api } from '../api';

export default function ScheduledPage() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listScheduledJobs()
      .then(res => setJobs(res.data || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  function formatTime(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('en-US', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  }

  if (loading) return <div className="empty-state"><p>Loading...</p></div>;

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1>Scheduled Jobs</h1>
        <p>Cron-based recurring job definitions</p>
      </div>
      <div className="card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Cron</th>
              <th>Status</th>
              <th>Last run</th>
              <th>Next run</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map(j => (
              <tr key={j.id}>
                <td style={{ fontWeight: 500 }}>{j.name}</td>
                <td className="mono">{j.cron_expression}</td>
                <td>
                  <span className={`badge ${j.is_active ? 'badge-online' : 'badge-cancelled'}`}>
                    {j.is_active ? 'active' : 'paused'}
                  </span>
                </td>
                <td className="timestamp">{formatTime(j.last_run_at)}</td>
                <td className="timestamp">{formatTime(j.next_run_at)}</td>
              </tr>
            ))}
            {jobs.length === 0 && (
              <tr>
                <td colSpan={5} className="empty-state">No scheduled jobs</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
