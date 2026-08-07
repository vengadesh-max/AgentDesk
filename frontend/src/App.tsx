import { Navigate, Outlet, Link, useLocation } from 'react-router-dom';
import { useAuth } from './context/AuthContext';

function Layout() {
  const { logout } = useAuth();
  const location = useLocation();

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">A</div>
          <div>
            <h2>AgentDesk</h2>
            <span>Chatbot platform</span>
          </div>
        </div>
        <nav>
          <Link to="/" className={location.pathname === '/' ? 'active' : ''}>
            Agents
          </Link>
        </nav>
        <div className="sidebar-account">
          <button className="btn-secondary" onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>
      <main className={`main ${location.pathname.startsWith('/projects/') ? 'project-main' : ''}`}>
        <Outlet />
      </main>
    </div>
  );
}

function ProtectedRoute() {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <Layout />;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Loading...</div>;
  if (user) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export { Layout, ProtectedRoute, PublicRoute };
