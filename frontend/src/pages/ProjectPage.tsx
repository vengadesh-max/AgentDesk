import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api, Conversation, Message, Project, Prompt, ProjectFile } from '../api';

type Tab = 'chat' | 'prompts' | 'settings' | 'files';

function FormattedMessage({ content }: { content: string }) {
  const lines = content.split('\n');
  return (
    <div className="md-content">
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        if (['•', '-', '*'].includes(trimmed)) return null;
        if (!trimmed) return <div key={idx} style={{ height: '0.4rem' }} />;

        const isBullet = trimmed.startsWith('- ') || trimmed.startsWith('* ') || trimmed.startsWith('• ') || trimmed.startsWith('•');
        let textContent = line;
        if (isBullet) {
          textContent = trimmed.replace(/^[•\-\*]\s*/, '');
          if (!textContent.trim()) return null;
        }

        const parts = textContent.split(/(\*\*.*?\*\*|\*.*?\*|`.*?`)/g);
        const renderedParts = parts.map((part, pIdx) => {
          if (part.startsWith('**') && part.endsWith('**')) {
            return <strong key={pIdx}>{part.slice(2, -2)}</strong>;
          }
          if (part.startsWith('*') && part.endsWith('*')) {
            return <em key={pIdx}>{part.slice(1, -1)}</em>;
          }
          if (part.startsWith('`') && part.endsWith('`')) {
            return <code key={pIdx} className="inline-code">{part.slice(1, -1)}</code>;
          }
          return part;
        });

        if (isBullet) {
          return (
            <div key={idx} className="md-bullet">
              <span className="bullet-dot">•</span>
              <span>{renderedParts}</span>
            </div>
          );
        }

        return <div key={idx} className="md-line">{renderedParts}</div>;
      })}
    </div>
  );
}

export default function ProjectPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [tab, setTab] = useState<Tab>('chat');
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState('');
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!projectId) return;
    api.listProjects().then((list) => {
      const p = list.find((x) => x.id === projectId);
      if (p) setProject(p);
    });
    api.listConversations(projectId).then(setConversations);
    api.listPrompts(projectId).then(setPrompts);
    api.listFiles(projectId).then(setFiles);
  }, [projectId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadConversation = async (convId: string) => {
    if (!projectId) return;
    setActiveConversation(convId);
    const conv = await api.getConversation(projectId, convId);
    setMessages(conv.messages);
  };

  const startNewChat = () => {
    setActiveConversation(null);
    setMessages([]);
  };

  const handleDeleteConversation = async (e: React.MouseEvent, convId: string) => {
    e.stopPropagation();
    if (!projectId) return;
    if (!confirm('Are you sure you want to delete this chat conversation?')) return;
    try {
      await api.deleteConversation(projectId, convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConversation === convId) {
        startNewChat();
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete chat');
    }
  };

  const handleToggleStarConversation = async (e: React.MouseEvent, conv: Conversation) => {
    e.stopPropagation();
    if (!projectId) return;
    try {
      const newStarred = !conv.is_starred;
      const updated = await api.updateConversation(projectId, conv.id, { is_starred: newStarred });
      setConversations((prev) =>
        prev
          .map((c) => (c.id === conv.id ? { ...c, is_starred: updated.is_starred } : c))
          .sort((a, b) => (Number(b.is_starred || false) - Number(a.is_starred || false)))
      );
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to update star status');
    }
  };

  const sendMessage = async () => {
    if (!projectId || !input.trim() || sending) return;
    setSending(true);
    setChatError('');
    const text = input.trim();
    setInput('');

    const tempUserMsg: Message = {
      id: 'temp-user',
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const res = await api.sendMessage(projectId, text, activeConversation || undefined);
      if (!activeConversation) {
        setActiveConversation(res.conversation_id);
        const convs = await api.listConversations(projectId);
        setConversations(convs);
      }
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== 'temp-user'),
        res.user_message,
        res.assistant_message,
      ]);
    } catch (err) {
      setMessages((prev) => prev.filter((m) => m.id !== 'temp-user'));
      setChatError(err instanceof Error ? err.message : 'Failed to send message');
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  if (!project) return <div className="loading">Loading agent...</div>;

  return (
    <div className="project-page">
      <div className="page-header project-header">
        <div>
          <p className="eyebrow">Agent</p>
          <h1>{project.name}</h1>
          <p className="page-subtitle">{project.description || 'No description added yet.'}</p>
        </div>
        <div className="project-stats">
          <span>{prompts.length} prompts</span>
          <span>{files.length} files</span>
          <span>{conversations.length} chats</span>
        </div>
      </div>

      <div className="tabs">
        {(['chat', 'prompts', 'files', 'settings'] as Tab[]).map((t) => (
          <button key={t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === 'chat' && (
        <div className="chat-layout">
          <div className="chat-sidebar">
            <button className="btn-secondary new-chat-button" onClick={startNewChat}>
              New chat
            </button>
            <div className="conversation-list">
              {conversations.length === 0 && <p className="sidebar-empty">No conversations yet.</p>}
              {conversations.map((c) => (
                <div
                  key={c.id}
                  className={`chat-sidebar-item ${activeConversation === c.id ? 'active' : ''} ${c.is_starred ? 'starred' : ''}`}
                  onClick={() => loadConversation(c.id)}
                >
                  <div className="chat-sidebar-item-info">
                    <span>{c.is_starred ? '⭐ ' : ''}{c.title || 'Untitled'}</span>
                    <small>{new Date(c.created_at).toLocaleDateString()}</small>
                  </div>
                  <div className="chat-sidebar-actions">
                    <button
                      className={`btn-star-conv ${c.is_starred ? 'active' : ''}`}
                      title={c.is_starred ? 'Unstar conversation' : 'Star conversation'}
                      onClick={(e) => handleToggleStarConversation(e, c)}
                    >
                      {c.is_starred ? '⭐' : '☆'}
                    </button>
                    <button
                      className="btn-delete-conv"
                      title="Delete conversation"
                      onClick={(e) => handleDeleteConversation(e, c.id)}
                    >
                      🗑️
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="chat-main">
            <div className="chat-messages">
              {messages.length === 0 && (
                <div className="chat-empty">
                  <h2>Ask {project.name}</h2>
                  <p>Responses use Groq. The agent will combine its system prompt, saved prompts, and conversation history.</p>
                  <div className="suggestion-grid">
                    {[
                      'Summarize this agent configuration',
                      'Draft a concise customer reply',
                      'What context do you have?',
                    ].map((suggestion) => (
                      <button key={suggestion} className="suggestion" onClick={() => setInput(suggestion)}>
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {messages.map((m) => (
                <div key={m.id} className={`message ${m.role}`}>
                  <span className="message-role">{m.role === 'user' ? 'You' : 'BOT'}</span>
                  {m.role === 'user' ? m.content : <FormattedMessage content={m.content} />}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
            <div className="composer-wrap">
              {chatError && <p className="error">{chatError}</p>}
              <div className="chat-input">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask anything about this agent..."
                  rows={1}
                />
                <button className="btn-primary" onClick={sendMessage} disabled={sending || !input.trim()}>
                  {sending ? 'Sending' : 'Send'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'prompts' && <PromptsTab projectId={projectId!} prompts={prompts} setPrompts={setPrompts} />}
      {tab === 'files' && <FilesTab projectId={projectId!} files={files} setFiles={setFiles} />}
      {tab === 'settings' && <SettingsTab project={project} setProject={setProject} />}
    </div>
  );
}

function PromptsTab({
  projectId,
  prompts,
  setPrompts,
}: {
  projectId: string;
  prompts: Prompt[];
  setPrompts: (p: Prompt[]) => void;
}) {
  const [name, setName] = useState('');
  const [content, setContent] = useState('');

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const prompt = await api.createPrompt(projectId, { name, content });
    setPrompts([prompt, ...prompts]);
    setName('');
    setContent('');
  };

  const handleDelete = async (id: string) => {
    await api.deletePrompt(projectId, id);
    setPrompts(prompts.filter((p) => p.id !== id));
  };

  return (
    <div>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Prompt library</p>
            <h2>Add reusable context</h2>
          </div>
        </div>
        <form onSubmit={handleCreate}>
          <div className="form-group">
            <label>Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="form-group">
            <label>Content</label>
            <textarea value={content} onChange={(e) => setContent(e.target.value)} required rows={4} />
          </div>
          <button type="submit" className="btn-primary">Save prompt</button>
        </form>
      </section>
      {prompts.length === 0 ? (
        <div className="empty-state empty-panel"><p>No prompts saved yet.</p></div>
      ) : (
        prompts.map((p) => (
          <div key={p.id} className="prompt-item">
            <div>
              <h4>{p.name}</h4>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                {p.content.slice(0, 120)}{p.content.length > 120 ? '...' : ''}
              </p>
            </div>
            <button className="btn-danger" onClick={() => handleDelete(p.id)}>Delete</button>
          </div>
        ))
      )}
    </div>
  );
}

function FilesTab({
  projectId,
  files,
  setFiles,
}: {
  projectId: string;
  files: ProjectFile[];
  setFiles: (f: ProjectFile[]) => void;
}) {
  const [uploading, setUploading] = useState(false);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const uploaded = await api.uploadFile(projectId, file);
      setFiles([uploaded, ...files]);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleDelete = async (id: string) => {
    await api.deleteFile(projectId, id);
    setFiles(files.filter((f) => f.id !== id));
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Files</p>
            <h2>Attach project material</h2>
          </div>
        </div>
        <input type="file" onChange={handleUpload} disabled={uploading} />
        {uploading && <p style={{ marginTop: '0.5rem', color: 'var(--text-muted)' }}>Uploading...</p>}
      </section>
      {files.length === 0 ? (
        <div className="empty-state empty-panel"><p>No files uploaded yet.</p></div>
      ) : (
        files.map((f) => (
          <div key={f.id} className="file-item">
            <div>
              <span>{f.original_name}</span>
              <span className="badge" style={{ marginLeft: '0.5rem' }}>{formatSize(f.size_bytes)}</span>
              {f.openai_file_id && <span className="badge" style={{ marginLeft: '0.5rem' }}>LLM synced</span>}
            </div>
            <button className="btn-danger" onClick={() => handleDelete(f.id)}>Delete</button>
          </div>
        ))
      )}
    </div>
  );
}

function SettingsTab({
  project,
  setProject,
}: {
  project: Project;
  setProject: (p: Project) => void;
}) {
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description || '');
  const [systemPrompt, setSystemPrompt] = useState(project.system_prompt || '');
  const [saved, setSaved] = useState(false);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const updated = await api.updateProject(project.id, {
      name,
      description,
      system_prompt: systemPrompt,
    });
    setProject(updated);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <section className="panel settings-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Settings</p>
          <h2>Agent settings</h2>
        </div>
      </div>
      <form onSubmit={handleSave}>
        <div className="form-group">
          <label>Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </div>
        <div className="form-group">
          <label>Description</label>
          <input value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <div className="form-group">
          <label>System Prompt</label>
          <textarea value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} rows={6} />
        </div>
        <button type="submit" className="btn-primary">
          {saved ? 'Saved' : 'Save changes'}
        </button>
      </form>
    </section>
  );
}
