import { useEffect, useState } from 'react';
import { api } from '../api';

export default function QueuesPage() {
  const [queues, setQueues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newQueue, setNewQueue] = useState({
    name: '',
    slug: '',
    description: '',
    priority: 1,
    concurrency_limit: 10
  });

  useEffect(() => {
    loadQueues();
  }, []);

  async function loadQueues() {
    try {
      const res = await api.listQueues();
      setQueues(res.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function togglePause(queue) {
    try {
      if (queue.is_paused) {
        await api.resumeQueue(queue.id);
      } else {
        await api.pauseQueue(queue.id);
      }
      loadQueues();
    } catch (err) {
      console.error(err);
    }
  }

  async function handleCreateQueue(e) {
    e.preventDefault();
    try {
      await api.createQueue(newQueue);
      setShowCreateForm(false);
      setNewQueue({ name: '', slug: '', description: '', priority: 1, concurrency_limit: 10 });
      loadQueues();
    } catch (err) {
      console.error("Failed to create queue", err);
      alert(err.message || "Failed to create queue");
    }
  }

  if (loading) return <div className="empty-state"><p>Loading...</p></div>;

  return (
    <div className="fade-in">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Queues</h1>
          <p>Manage job queues and their configuration</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreateForm(!showCreateForm)}>
          {showCreateForm ? 'Cancel' : '+ Create Queue'}
        </button>
      </div>

      {showCreateForm && (
        <div className="card" style={{ marginBottom: '24px' }}>
          <h3 style={{ marginTop: 0, marginBottom: '16px' }}>Create New Queue</h3>
          <form onSubmit={handleCreateQueue}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
              <div className="form-group">
                <label className="form-label">Name</label>
                <input required className="form-input" type="text" value={newQueue.name} onChange={e => setNewQueue({...newQueue, name: e.target.value})} placeholder="e.g., Image Processing" />
              </div>
              <div className="form-group">
                <label className="form-label">Slug</label>
                <input required className="form-input" type="text" value={newQueue.slug} onChange={e => setNewQueue({...newQueue, slug: e.target.value})} placeholder="e.g., image-processing" />
              </div>
              <div className="form-group">
                <label className="form-label">Priority</label>
                <input type="number" className="form-input" value={newQueue.priority} onChange={e => setNewQueue({...newQueue, priority: parseInt(e.target.value)})} />
              </div>
              <div className="form-group">
                <label className="form-label">Concurrency Limit</label>
                <input type="number" className="form-input" value={newQueue.concurrency_limit} onChange={e => setNewQueue({...newQueue, concurrency_limit: parseInt(e.target.value)})} />
              </div>
            </div>
            <div className="form-group" style={{ marginBottom: '24px' }}>
              <label className="form-label">Description</label>
              <input type="text" className="form-input" value={newQueue.description} onChange={e => setNewQueue({...newQueue, description: e.target.value})} placeholder="Queue description..." />
            </div>
            <div style={{ display: 'flex', gap: '12px' }}>
              <button type="submit" className="btn btn-primary">Create Queue</button>
              <button type="button" className="btn" onClick={() => setShowCreateForm(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Slug</th>
              <th>Priority</th>
              <th>Concurrency</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {queues.map(q => (
              <tr key={q.id}>
                <td style={{ fontWeight: 500 }}>{q.name}</td>
                <td className="mono">{q.slug}</td>
                <td>{q.priority}</td>
                <td>{q.concurrency_limit || '∞'}</td>
                <td>
                  <span className={`badge ${q.is_paused ? 'badge-cancelled' : 'badge-online'}`}>
                    {q.is_paused ? 'paused' : 'active'}
                  </span>
                </td>
                <td>
                  <button className="btn btn-sm" onClick={() => togglePause(q)}>
                    {q.is_paused ? 'Resume' : 'Pause'}
                  </button>
                </td>
              </tr>
            ))}
            {queues.length === 0 && (
              <tr>
                <td colSpan={6} className="empty-state">No queues configured</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
