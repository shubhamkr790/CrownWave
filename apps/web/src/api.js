const API_BASE = '/api/v1';

class ApiClient {
  constructor() {
    this.token = localStorage.getItem('access_token');
  }

  setToken(token) {
    this.token = token;
    localStorage.setItem('access_token', token);
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }

  async request(path, options = {}) {
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      this.clearToken();
      window.location.href = '/login';
      throw new Error('Session expired');
    }

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'Request failed');
    }
    return data;
  }

  // Auth
  login(email, password) {
    return this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  }

  register(email, password, displayName, orgName) {
    return this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password,
        display_name: displayName,
        org_name: orgName,
      }),
    });
  }

  getMe() {
    return this.request('/auth/me');
  }

  // Jobs
  listJobs(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request(`/jobs?${qs}`);
  }

  getJob(id) {
    return this.request(`/jobs/${id}`);
  }

  enqueueJob(data) {
    return this.request('/jobs', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  retryJob(id) {
    return this.request(`/jobs/${id}/retry`, { method: 'POST' });
  }

  cancelJob(id) {
    return this.request(`/jobs/${id}/cancel`, { method: 'POST' });
  }

  // Queues
  listQueues() {
    return this.request('/queues');
  }

  getQueue(id) {
    return this.request(`/queues/${id}`);
  }

  createQueue(data) {
    return this.request('/queues', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  pauseQueue(id) {
    return this.request(`/queues/${id}/pause`, { method: 'POST' });
  }

  resumeQueue(id) {
    return this.request(`/queues/${id}/resume`, { method: 'POST' });
  }

  // Workers
  listWorkers() {
    return this.request('/workers');
  }

  getWorker(id) {
    return this.request(`/workers/${id}`);
  }

  // Metrics
  getOverview() {
    return this.request('/metrics/overview');
  }

  // DLQ
  listDlq(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request(`/dlq?${qs}`);
  }

  replayDlqEntry(id) {
    return this.request(`/dlq/${id}/replay`, { method: 'POST' });
  }

  resolveDlqEntry(id) {
    return this.request(`/dlq/${id}/resolve`, { method: 'POST' });
  }

  // Scheduled Jobs
  listScheduledJobs() {
    return this.request('/scheduled-jobs');
  }

  createScheduledJob(data) {
    return this.request('/scheduled-jobs', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }
}

export const api = new ApiClient();
