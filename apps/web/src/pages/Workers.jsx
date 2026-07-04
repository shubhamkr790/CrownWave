import { useEffect, useState } from 'react';
import { api } from '../api';

export default function WorkersPage() {
  const [workers, setWorkers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listWorkers()
      .then(res => setWorkers(res.data || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  function formatTime(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('en-US', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }

  function timeAgo(iso) {
    if (!iso) return 'never';
    const diff = Date.now() - new Date(iso).getTime();
    const sec = Math.floor(diff / 1000);
    if (sec < 60) return `${sec}s ago`;
    if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
    return `${Math.floor(sec / 3600)}h ago`;
  }

  if (loading) return <div className="empty-state"><p>Loading...</p></div>;

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1>Workers</h1>
        <p>Active and historical worker instances</p>
      </div>

      <div className="card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Queues</th>
              <th>Last heartbeat</th>
              <th>Started</th>
            </tr>
          </thead>
          <tbody>
            {workers.map(w => (
              <tr key={w.id}>
                <td className="mono" style={{ fontWeight: 500 }}>{w.name}</td>
                <td>
                  <span className={`badge badge-${w.status}`}>{w.status}</span>
                </td>
                <td className="mono">{w.queue_filter}</td>
                <td className="timestamp">{timeAgo(w.last_heartbeat_at)}</td>
                <td className="timestamp">{formatTime(w.started_at)}</td>
              </tr>
            ))}
            {workers.length === 0 && (
              <tr>
                <td colSpan={5} className="empty-state">No workers registered</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
