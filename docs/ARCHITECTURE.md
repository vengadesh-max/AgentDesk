# Architecture & Design Document

## Overview

The Chatbot Platform (AgentDesk) is a full-stack web application that enables users to create AI agents (projects), configure system prompts and prompt libraries, upload reference files, and interact via a fast chat interface powered by **[Groq AI](https://console.groq.com)** (with automatic local offline fallback).

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client (Browser)                      │
│            React SPA — Auth, Dashboard, BOT Chat UI          │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS / REST + JWT
┌──────────────────────────▼──────────────────────────────────┐
│                     FastAPI Backend                         │
│  ┌─────────┐ ┌──────────┐ ┌──────┐ ┌──────────┐ ┌───────┐ │
│  │  Auth   │ │ Projects │ │ Chat │ │ Prompts  │ │ Files │ │
│  │ (JWT)   │ │  Router  │ │Router│ │  Router  │ │Router │ │
│  └────┬────┘ └────┬─────┘ └──┬───┘ └────┬─────┘ └───┬───┘ │
│       └───────────┴──────────┴──────────┴───────────┘     │
│                           │                                  │
│                    SQLAlchemy ORM                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
         ┌─────────────────┴─────────────────┐
         │                                   │
    ┌────▼────────┐                    ┌─────▼───────┐
    │ PostgreSQL /│                    │  Groq API   │
    │   SQLite    │                    │(console.groq)│
    └─────────────┘                    └─────────────┘
```

---

## Technology Breakdown

| Layer | Technology | Role & Rationale |
|-------|-----------|------------------|
| Frontend Tooling | Node.js + Vite | Node.js runs Vite dev/build server; compiles React 18 + TypeScript SPA |
| Backend Runtime | FastAPI (Python 3.12) | High-performance async REST API, ORM schema handling, LLM provider integration |
| Database | PostgreSQL 16 / SQLite | PostgreSQL for production (ACID compliance & pooling); SQLite for zero-config dev |
| Auth & Security | JWT (python-jose) + bcrypt | Stateless authentication tokens & secure salted password hashing |
| LLM Provider | Groq API | High-speed LLM inference powered by `llama-3.1-8b-instant` with offline fallback |
| Infrastructure | Docker & Docker Compose | Containerized orchestration for frontend (nginx), backend, and database |

---

## Data Model

```
User (1) ──── (N) Project
                    │
                    ├── (N) Prompt
                    ├── (N) Conversation ──── (N) Message
                    └── (N) ProjectFile
```

### Entities

- **User**: Account credentials (`email`, `hashed_password`, `full_name`, `created_at`)
- **Project**: Agent container (`name`, `description`, `system_prompt`, `owner_id`)
- **Prompt**: Saved reusable prompt snippets (`name`, `content`, `project_id`)
- **Conversation**: Chat session thread (`title`, `project_id`, `created_at`)
- **Message**: Chat entry (`role`: `user` | `assistant`, `content`, `conversation_id`)
- **ProjectFile**: Attached reference documents (`filename`, `original_name`, `openai_file_id`)

---

## Key Workflows

### 1. Authentication Flow
1. User registers (`POST /api/auth/register`) or logs in (`POST /api/auth/login`).
2. Password is verified against bcrypt hash.
3. JWT access token is signed (24h expiry) and returned to client localStorage.
4. Client attaches `Authorization: Bearer <token>` to all protected endpoints.

### 2. Groq LLM Response Pipeline
1. User sends message via `POST /api/projects/{id}/chat`.
2. Backend persists user message to database.
3. Context assembly combines:
   - System prompt configuration
   - Saved prompt library snippets
   - Historical conversation messages (sanitized to prevent payload duplication)
4. Payload is dispatched to **[Groq API](https://console.groq.com)** (`llama-3.1-8b-instant`).
5. Assistant response is saved under `assistant` role and displayed as **`BOT`** in the chat UI.
6. *Fallback*: If no Groq key is set or quota is exceeded, local fallback generator safely responds without throwing system crashes.

---

## How to Test Easily

1. Get a free API Key from **[https://console.groq.com](https://console.groq.com)**.
2. Add key to `.env`:
   ```env
   GROQ_API_KEY=gsk_...
   LLM_PROVIDER=groq
   GROQ_MODEL=llama-3.1-8b-instant
   ```
3. Run with Docker: `docker compose up --build -d`
4. Open `http://localhost:3000`, register an account, create an agent, and send a message!

---

## Non-Functional Requirements Implementation

- **Scalability**: Stateless FastAPI design allowing backend scaling behind load balancers.
- **Security**: Strict user-level data isolation (`owner_id` verification on all endpoints), bcrypt password encryption, and CORS origin restriction. API keys stored strictly in `.env`.
- **Extensibility**: Service module architecture (`app/services/`) facilitating seamless addition of vector stores (RAG), webhooks, or analytics endpoints.
- **Performance**: Non-blocking async API endpoints, database index optimization, and lightweight Vite bundle.
- **Reliability**: Structured error responses, rate-limiting guards, and resilient fallback to simulated offline responses when LLM quota or API keys are unavailable.
