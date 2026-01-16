# The Task

You have been given a simple Django-based chat application that connects users to an AI assistant. Currently, the system handles basic conversations but provides no way to understand whether users find the AI responses helpful or not. 

Your task is to build a mechanism that captures user feedback and transforms that data into actionable insights. Additionally, build a screen where we can see those insights and statistics.

How else can you improve the application?

## Guidelines
1. Please fork this repository and send us the url.
2. We expect you to spend roughly 60 minutes.
3. We want to see how you think and your decision making process.
4. We expect you to use AI heavily to help with this task.
5. If you have any issues, please reach out to us.

## Deliverables
1. Working Code with setup instructions
2. AI_PROMPTS.md - All prompts used, organized chronologically
3. DECISIONS.md - What decisions you made and why. This **should not** be AI generated. Use your own words.

## Technical Overview
- Backend: Django 5 + DRF, SQLite for local dev
- Frontend: Vite + TypeScript + Tailwind, built to `static/app/`
- AI: Google Gemini via `google-genai` (no streaming)

### Prerequisites

- Python 3.11+
- uv (https://docs.astral.sh/uv/) for Python deps
- Node.js 18+ (recommended 20+) and npm

### Setup

1. Install Python deps
   - `make uv-sync`
2. Env vars
   - `cp .env.example .env`
   - Set `GEMINI_API_KEY` in `.env`
3. Initialize DB
   - `make migrate`
4. Build frontend assets
   - `make build-frontend`

### Run (development)

- Start Django dev server:
  - `make run`
  - Requires `GEMINI_API_KEY` to be set; the server exits with an error if missing.
- Open `http://127.0.0.1:8000/` — the Vite-built app is served via Django templates.

### APIs

- `POST /api/conversations/` → create conversation (optional `title`)
- `GET /api/conversations/?offset=&limit=` → list conversations (newest first)
- `GET /api/conversations/{id}/` → conversation details
- `GET /api/conversations/{id}/messages?since=&limit=` → list messages after sequence
- `POST /api/conversations/{id}/messages/` → send user message; returns `{ user_message, ai_message }`

### Tests

- `make test`

### Notes

- If `GEMINI_API_KEY` is missing, sending a message returns HTTP 502 with a clear error.
- The frontend polling interval is 3s; max message length is 1000 chars.
- The dev server for Vite (`npm run dev`) is available but not wired into templates; the template loads built assets from `static/app/`. If you want HMR, we can add a dev switch.
