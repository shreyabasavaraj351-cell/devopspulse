# DevOpsPulse

An AI DevOps assistant that analyses deployment failures, **remembers previous incidents across sessions**, and uses that memory to recommend actions for future deployments.

- **Frontend:** React + Vite
- **Backend:** Python + FastAPI
- **AI:** Groq (log analysis, reasoning, recommendations)
- **Memory:** Hindsight (retain, recall, reflect)
- **Database:** PostgreSQL (users, projects, deployments, incidents, feedback, audit). SQLite works for quick local dev.

## How the agent works

1. User uploads or pastes a deployment log.
2. The backend redacts secrets, cleans the log and scans for errors.
3. **Groq** diagnoses the failure: root cause, category, severity, suggested resolution.
4. **Hindsight recall** searches this project's memory for similar past incidents.
5. **Groq** refines the recommendation using the recalled memories and says which memory influenced it.
6. The incident is saved, and **Hindsight retain** stores it, marked as an *unverified* suggestion.
7. The user later confirms the outcome. Only then is the resolution stored as **verified** and retained in memory.

A suggested fix is never treated as a verified fix until the user confirms it.

## How Hindsight is used

| Hindsight operation | Where | Purpose |
| --- | --- | --- |
| `retain` | After every analysed failure, and after every outcome confirmation | Stores incident details, then the confirmed result |
| `recall` | Deployment analysis, risk prediction, AI assistant, memory explorer | Finds similar past incidents |
| `reflect` | AI assistant | Reasons over accumulated experience to answer questions |

Each project gets its own memory bank (`pm-org{org_id}-proj{project_id}`), so memory retrieval is restricted to the user's authorised project. PostgreSQL stores records; it does not replace Hindsight.

## Setup

### 1. Environment

```bash
cp .env.example backend/.env
# edit backend/.env: SECRET_KEY, GROQ_API_KEY, HINDSIGHT_BASE_URL / HINDSIGHT_API_KEY, DATABASE_URL
```

For a quick start without Postgres, keep the SQLite `DATABASE_URL` value in your existing environment configuration.

### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs. Tables are created on startup.

### 3. Frontend

```bash
cd frontend
cp .env.example .env      # VITE_API_URL=http://localhost:8000
npm install
npm run dev
```

Open http://localhost:5173.

> **Verify the Hindsight SDK.** `backend/app/memory/hindsight_service.py` calls `retain`, `recall` and `reflect` on the `hindsight-client` package. Check the method names and arguments against the version you install and the Hindsight docs. All memory calls fail gracefully, so the app keeps working if Hindsight is unreachable.

### Password reset

No email provider is wired up. The reset link is printed in the backend console when you use "Forgot password".

## Demo script

Sample logs are in `sample_logs/`.

1. Register, complete onboarding, log in.
2. **Analyse deployment**: upload `01_db_migration_failure.log`. Show the root cause and recommendation. The incident is retained in Hindsight (check the Memory explorer timeline).
3. Open the incident and, if you want the agent to learn it as verified, submit the outcome (or skip to step 4 to show the recall of an unverified memory).
4. Start a fresh session (log out and back in, or open a new browser). Upload `02_db_migration_failure_similar.log`.
5. Show the recommendation with **"Informed by memory"** and the recalled incident.
6. Open the Memory explorer to show which memory influenced the advice.
7. Open the new incident and submit the confirmed outcome. Show it retained for future use.
8. Try the Risk prediction and AI assistant pages. `04_successful_deploy.log` shows a clean run that creates no incident.

## API

| Endpoint | Purpose |
| --- | --- |
| `POST /auth/register`, `/auth/login`, `/auth/forgot-password`, `/auth/reset-password` · `GET /auth/me` | Authentication |
| `POST /onboarding` · `GET/POST /projects` | Team and project setup |
| `GET /dashboard/summary` | Dashboard metrics |
| `POST /deployments/analyze` · `GET /deployments` · `GET /deployments/{id}` | Analysis and deployments |
| `GET /incidents` · `GET /incidents/{id}` · `POST /incidents/{id}/feedback` | Incidents and outcomes |
| `GET /memory` · `POST /memory/recall` | Memory activity and recall |
| `POST /risk/analyze` | Risk assessment |
| `POST /assistant/chat` | Memory-aware assistant |
| `GET /settings/integrations` · `PATCH /settings/profile` · `POST /settings/change-password` | Settings |

## Security notes

- Passwords hashed with bcrypt; JWT-protected routes; every query is scoped to the user's organisation.
- API keys stay in the backend `.env`; the frontend only receives booleans for integration status.
- Secrets in logs (passwords, tokens, API keys, connection-string credentials, private keys) are redacted **before** storage or any AI call. Only a redacted excerpt is stored, never the full log.
- Uploads are limited by type (`.log`, `.txt`, `.out`) and size (`MAX_UPLOAD_BYTES`).
- LLM output is validated against strict schemas before display. Logs and memories are passed to the model as untrusted data.
- Important actions are written to `audit_logs`.

## Testing checklist

Manual checks matching the hackathon brief:

1. Register and log in.
2. Protected pages redirect to login when signed out.
3. Upload a log; invalid file type and oversized files are rejected.
4. Groq returns a root cause for a sample log.
5. Hindsight retains the incident (Memory explorer timeline).
6. A later, separate session recalls it.
7. The new recommendation is memory-informed.
8. Submit feedback; dashboard counts update.
9. A second user's account cannot see the first user's incidents or memory (separate organisation and memory bank).
10. Stop Groq/Hindsight (blank the key or URL) and confirm the app degrades gracefully with a visible warning.
11. Repeat on the deployed URL, not just localhost.

## Project layout

```
devopspulse/
├── frontend/   React + Vite (pages, components, services, context)
├── backend/    FastAPI (routes, services, models, schemas, core, memory, ai)
├── sample_logs/
├── .env.example
└── README.md
```
