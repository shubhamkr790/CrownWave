import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isRegister, setIsRegister] = useState(false);
  const [displayName, setDisplayName] = useState('');
  const [orgName, setOrgName] = useState('');
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');

    try {
      let response;
      if (isRegister) {
        response = await api.register(email, password, displayName, orgName);
      } else {
        response = await api.login(email, password);
      }

      const tokens = response.data;
      api.setToken(tokens.access_token);
      localStorage.setItem('refresh_token', tokens.refresh_token);
      navigate('/');
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>{isRegister ? 'Create account' : 'Sign in'}</h1>
        <p>{isRegister ? 'Set up your workspace' : 'Access your job scheduler'}</p>

        {error && <div className="login-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          {isRegister && (
            <>
              <div className="form-group">
                <label className="form-label" htmlFor="displayName">Name</label>
                <input
                  id="displayName"
                  className="form-input"
                  value={displayName}
                  onChange={e => setDisplayName(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="orgName">Organization</label>
                <input
                  id="orgName"
                  className="form-input"
                  value={orgName}
                  onChange={e => setOrgName(e.target.value)}
                  required
                />
              </div>
            </>
          )}

          <div className="form-group">
            <label className="form-label" htmlFor="email">Email</label>
            <input
              id="email"
              className="form-input"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password">Password</label>
            <input
              id="password"
              className="form-input"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: '100%', justifyContent: 'center', marginBottom: 'var(--space-3)' }}
          >
            {isRegister ? 'Create account' : 'Sign in'}
          </button>
        </form>

        <button
          onClick={() => setIsRegister(!isRegister)}
          style={{
            background: 'none', border: 'none', color: 'var(--blue-600)',
            fontSize: '0.8125rem', cursor: 'pointer',
          }}
        >
          {isRegister ? 'Already have an account? Sign in' : "Don't have an account? Register"}
        </button>
      </div>
    </div>
  );
}
