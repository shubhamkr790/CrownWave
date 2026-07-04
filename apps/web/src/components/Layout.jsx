import { NavLink, Outlet } from 'react-router-dom';
import { api } from '../api';

const navItems = [
  { label: 'Overview', path: '/', section: 'Dashboard' },
  { label: 'Queues', path: '/queues', section: 'Resources' },
  { label: 'Jobs', path: '/jobs', section: 'Resources' },
  { label: 'Workers', path: '/workers', section: 'Resources' },
  { label: 'Scheduled', path: '/scheduled', section: 'Automation' },
  { label: 'Dead Letters', path: '/dlq', section: 'Operations' },
];

export default function Layout() {
  const sections = {};
  navItems.forEach(item => {
    if (!sections[item.section]) sections[item.section] = [];
    sections[item.section].push(item);
  });

  function handleLogout() {
    api.clearToken();
    window.location.href = '/login';
  }

  return (
    <div className="app-layout">
      <nav className="sidebar">
        <div className="sidebar-logo">cronwave</div>

        {Object.entries(sections).map(([section, items]) => (
          <div className="sidebar-section" key={section}>
            <div className="sidebar-section-label">{section}</div>
            {items.map(item => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  `sidebar-link${isActive ? ' active' : ''}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </div>
        ))}

        <div className="sidebar-section" style={{ marginTop: 'auto' }}>
          <button
            className="sidebar-link"
            onClick={handleLogout}
            style={{ width: '100%', border: 'none', background: 'none', textAlign: 'left' }}
          >
            Sign out
          </button>
        </div>
      </nav>

      <main className="main-content fade-in">
        <Outlet />
      </main>
    </div>
  );
}
