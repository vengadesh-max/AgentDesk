const API_BASE = import.meta.env.VITE_API_URL || '/api';

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  created_at: string;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  system_prompt: string | null;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface Prompt {
  id: string;
  project_id: string;
  name: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  role: string;
  content: string;
  created_at: string;
}

export interface Conversation {
  id: string;
  project_id: string;
  title: string | null;
  created_at: string;
  messages: Message[];
}

export interface ProjectFile {
  id: string;
  project_id: string;
  filename: string;
  original_name: string;
  content_type: string | null;
  size_bytes: number;
  openai_file_id: string | null;
  created_at: string;
}

export function getToken(): string | null {
  return localStorage.getItem('token');
}

export function setToken(token: string) {
  localStorage.setItem('token', token);
}

export function clearToken() {
  localStorage.removeItem('token');
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    clearToken();
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    let message = res.statusText || 'Request failed';
    try {
      const err = await res.json();
      const detail = err.detail;
      if (typeof detail === 'string' && detail.trim()) {
        message = detail.replace(/^LLM service error:\s*/i, '');
      } else if (Array.isArray(detail)) {
        message = detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(', ') || message;
      }
    } catch {
      if (res.status === 502 || res.status === 503 || res.status === 504) {
        message = 'Backend unavailable. Run: docker compose up --build -d';
      }
    }
    throw new Error(message);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  register: (email: string, password: string, full_name?: string) =>
    request<{ access_token: string }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name }),
    }),

  login: (email: string, password: string) =>
    request<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<User>('/auth/me'),

  listProjects: () => request<Project[]>('/projects'),

  createProject: (data: { name: string; description?: string; system_prompt?: string }) =>
    request<Project>('/projects', { method: 'POST', body: JSON.stringify(data) }),

  updateProject: (id: string, data: Partial<Project>) =>
    request<Project>(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  deleteProject: (id: string) =>
    request<void>(`/projects/${id}`, { method: 'DELETE' }),

  listPrompts: (projectId: string) =>
    request<Prompt[]>(`/projects/${projectId}/prompts`),

  createPrompt: (projectId: string, data: { name: string; content: string }) =>
    request<Prompt>(`/projects/${projectId}/prompts`, { method: 'POST', body: JSON.stringify(data) }),

  deletePrompt: (projectId: string, promptId: string) =>
    request<void>(`/projects/${projectId}/prompts/${promptId}`, { method: 'DELETE' }),

  listConversations: (projectId: string) =>
    request<Conversation[]>(`/projects/${projectId}/chat/conversations`),

  getConversation: (projectId: string, conversationId: string) =>
    request<Conversation>(`/projects/${projectId}/chat/conversations/${conversationId}`),

  deleteConversation: (projectId: string, conversationId: string) =>
    request<void>(`/projects/${projectId}/chat/conversations/${conversationId}`, { method: 'DELETE' }),

  sendMessage: (projectId: string, message: string, conversationId?: string) =>
    request<{ conversation_id: string; user_message: Message; assistant_message: Message }>(
      `/projects/${projectId}/chat`,
      { method: 'POST', body: JSON.stringify({ message, conversation_id: conversationId }) },
    ),

  listFiles: (projectId: string) =>
    request<ProjectFile[]>(`/projects/${projectId}/files`),

  uploadFile: (projectId: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<ProjectFile>(`/projects/${projectId}/files`, { method: 'POST', body: form });
  },

  deleteFile: (projectId: string, fileId: string) =>
    request<void>(`/projects/${projectId}/files/${fileId}`, { method: 'DELETE' }),
};
