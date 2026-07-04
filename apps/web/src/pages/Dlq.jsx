import { useEffect, useState } from 'react';
import { api } from '../api';

export default function DlqPage() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadEntries(); }, []);

  async function loadEntries() {
    try {
      const res = await api.listDlq({ is_resolved: false });
      setEntries(res.data || []);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }

  if (loading) return <div className="empty-state"><p>Loading...</p></div>;

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1>Dead Letter Queue</h1>
        <p>Jobs that exhausted all retry attempts</p>
      </div>
      <div className="card">
        <table className="data-table">
          <thead>
            <tr><th>Job</th><th>Attempts</th><th>Error</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {entries.map(e => (
              <tr key={e.id}>
                <td style={{fontWeight:500}}>{e.job_name}</td>
                <td>{e.attempt_count}</td>
                <td style={{color:'var(--red-600)',maxWidth:'300px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{e.last_error||'—'}</td>
                <td>
                  <button className="btn btn-sm" onClick={()=>api.replayDlqEntry(e.id).then(loadEntries)}>Replay</button>
                  {' '}
                  <button className="btn btn-sm" onClick={()=>api.resolveDlqEntry(e.id).then(loadEntries)}>Resolve</button>
                </td>
              </tr>
            ))}
            {entries.length===0 && <tr><td colSpan={4} className="empty-state">No dead letter entries</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
