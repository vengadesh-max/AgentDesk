import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, Project } from '../api';

export default function DashboardPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    api.listProjects()
      .then(setProjects)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      const project = await api.createProject({
        name,
        description: description || undefined,
        system_prompt: systemPrompt || undefined,
      });
      setProjects((prev) => [project, ...prev]);
      setShowCreate(false);
      setName('');
      setDescription('');
      setSystemPrompt('');
      navigate(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create project');
    }
  };

  if (loading) return <div className="loading">Loading agents...</div>;

  const recentProjects = [...projects].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  );

  return (
    <div className="dashboard-page">
      <div className="page-header dashboard-header">
        <div>
          <p className="eyebrow">Workspace</p>
          <h1>Agents</h1>
          <p className="page-subtitle">Create project-scoped agents with prompts, files, and chat history.</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? 'Close' : 'New agent'}
        </button>
      </div>

      {showCreate && (
        <section className="create-agent-panel">
          <div>
            <p className="eyebrow">New agent</p>
            <h2>Define behavior up front</h2>
            <p>Give the agent a concise role. You can add reusable prompts and files after creation.</p>
          </div>
          <form onSubmit={handleCreate} className="agent-form">
            <div className="form-group">
              <label>Name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Customer Support Agent" />
            </div>
            <div className="form-group">
              <label>Description</label>
              <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Answers billing, product, and support questions" />
            </div>
            <div className="form-group">
              <label>System prompt</label>
              <textarea value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} placeholder="You are a precise customer support agent. Ask clarifying questions when needed." />
            </div>
            {error && <p className="error">{error}</p>}
            <button type="submit" className="btn-primary">Create agent</button>
          </form>
        </section>
      )}

      {projects.length === 0 ? (
        <section className="empty-state empty-panel">
          <h2>No agents yet</h2>
          <p>Create an agent, attach prompts, then start a project-scoped conversation.</p>
        </section>
      ) : (
        <div className="grid">
          {recentProjects.map((p) => (
            <div key={p.id} className="project-card" onClick={() => navigate(`/projects/${p.id}`)}>
              <div className="project-card-top">
                <div className="project-avatar">{p.name.slice(0, 1).toUpperCase()}</div>
                <span className="badge">Updated {new Date(p.updated_at).toLocaleDateString()}</span>
              </div>
              <h3>{p.name}</h3>
              <p>{p.description || 'No description added yet.'}</p>
              <div className="project-card-footer">
                <span>{p.system_prompt ? 'System prompt set' : 'No system prompt'}</span>
                <span>Open</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
