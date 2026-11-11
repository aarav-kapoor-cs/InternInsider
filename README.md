# InternInsider

A career copilot for students. Paste a resume, and it finds matching job postings, shows which skills are missing for a job, and prepares interview questions. A LangGraph agent with five tools does the work, job search runs on pgvector, and the same five tools are also exposed over MCP.

Stack: React + TypeScript (Vite), Python FastAPI, PostgreSQL with pgvector, LangGraph, MCP.

For interview prep, read [INTERVIEW_GUIDE.md](INTERVIEW_GUIDE.md) after this file.

## Architecture

```
 React page                     FastAPI                        PostgreSQL + pgvector
 ──────────                     ───────                        ─────────────────────
 search / match / gap  ─HTTP─▶  REST endpoints ─────────────▶  jobs table
                                      │                         (text + 384-number vector)
 chat message          ─HTTP─▶  /api/chat                            ▲
                                      │                              │ SQL
                                LangGraph agent                      │
                                 agent ⇄ tools  ── calls ──▶  tools.py (5 functions)
                                   │                                 ▲
                                   ▼                                 │
                                 OpenAI LLM              MCP server (same 5 functions,
                                                         for other AI apps)
```

The five tools in `tools.py` are plain Python functions. They are used from three places: the agent, the MCP server, and the REST endpoints. The left half of the page (search, match, skill gap) calls them directly and needs no API key. Only the chat needs the LLM.

## Files

```
backend/
  app/db.py          connection, table schema, embed() (text -> vector)
  app/skills.py      skill vocabulary and extract_skills()
  app/tools.py       the 5 tools
  app/agent.py       the LangGraph graph (agent node, tools node, loop)
  app/mcp_server.py  the same tools over MCP
  app/main.py        FastAPI endpoints
  app/ingest.py      loads job postings into the database
  data/sample_jobs.json   24 invented postings for an offline demo
  eval_retrieval.py  Recall@5: keyword search vs pgvector
  tests/test_app.py  11 tests
frontend/
  src/api.ts         fetch calls and types
  src/App.tsx        the three pages: Jobs, AI copilot, My resume
  src/styles.css     all the styling
start-backend.sh, start-frontend.sh
```

## Setup (Mac with Homebrew PostgreSQL)

Terminal 1:

```bash
cd ~/InternInsdier
bash start-backend.sh
```

The script starts PostgreSQL, creates the database, installs pgvector if it is missing, installs the Python packages, loads the sample postings, and runs the API on http://localhost:8001. The first run downloads a small embedding model. Wait for `Application startup complete.`

Terminal 2:

```bash
cd ~/InternInsdier
bash start-frontend.sh
```

Open http://localhost:5174.

### Add your OpenAI key (for the chat)

Open `backend/.env` (the start script creates it) and put your key after the `=`:

```
OPENAI_API_KEY=sk-...
```

Save, then stop the backend with Ctrl+C and run `bash start-backend.sh` again. The page header should say "AI chat ready". The default model is `gpt-5.4-mini`. To use another, add a line such as `LLM_MODEL=openai:gpt-4o-mini` to `.env`.

Never commit `.env`. It is in `.gitignore`.

### Tests

```bash
cd ~/InternInsdier/backend
source .venv/bin/activate
python -m pytest -v
```

The tests need no API key and no model download. They use a separate database, a simple stand-in embedder, and a scripted stand-in for the LLM.

### Real job postings

```bash
python -m app.ingest --remotive
```

This replaces the sample postings with about 100 real remote software jobs from the public Remotive API.

### Retrieval evaluation

```bash
python eval_retrieval.py
```

Prints Recall@5 for keyword search and for pgvector search on 12 queries, and reloads the sample postings first.

### Use the tools from another AI app (MCP)

`python -m app.mcp_server` runs the MCP server over stdio. To add it to Claude Desktop, put this in its `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "interninsider": {
      "command": "/Users/aaravkapoor/InternInsdier/backend/.venv/bin/python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/Users/aaravkapoor/InternInsdier/backend"
    }
  }
}
```

## Demo script (3 minutes)

1. Search "making apps for phones". The mobile jobs come up although none of them contains the word "phones". That is embedding search.
2. Paste a resume and click "Find jobs that match my resume".
3. Click "Skill gap" on a result. Have, missing, and a match percentage.
4. In the chat, ask "What am I missing for job 5?" and then "Give me interview questions for it". The grey line above each answer shows which tool the agent chose.
5. Run `python -m pytest -v`.

## API

| Method | Path | Body | What it does | Needs LLM |
|---|---|---|---|---|
| GET | `/api/health` | | Number of postings loaded, whether a key is set | no |
| GET | `/api/jobs` | | All postings (up to 60) | no |
| GET | `/api/jobs/search?q=...&limit=5` | | Embedding search over postings | no |
| POST | `/api/skills` | `{text}` | Skills found in a piece of text | no |
| GET | `/api/jobs/{id}` | | One posting in full (404 if unknown) | no |
| POST | `/api/match` | `{resume_text}` | Top postings for a resume, with matching skills | no |
| POST | `/api/skill-gap` | `{resume_text, job_id}` | Skills you have, skills missing, match percent | no |
| POST | `/api/chat` | `{message, resume_text?, history?}` | Runs the agent. Returns `{reply, tool_calls}`. 503 if no key, 502 if the LLM call fails | yes |

The agent's five tools: `search_jobs`, `get_job`, `match_resume`, `skill_gap`, `interview_prep`.

## Database schema

One table, `jobs`.

| Column | Type | Why it is there |
|---|---|---|
| `id` | SERIAL PRIMARY KEY | The job id the agent and the UI refer to |
| `title`, `company`, `location`, `category`, `url` | TEXT | Shown to the user |
| `description` | TEXT | The posting text |
| `skills` | TEXT[] | Skills found in the title and description at load time, so skill gap is a set comparison |
| `embedding` | vector(384) | The title and description turned into 384 numbers by the embedding model. Search compares these. |

There is an HNSW index on `embedding` with `vector_cosine_ops`. Search is one query:

```sql
SELECT ..., 1 - (embedding <=> $query_vector) AS similarity
FROM jobs ORDER BY embedding <=> $query_vector LIMIT 5;
```

`<=>` is cosine distance. Smaller distance means closer meaning.

## Demo-only shortcuts

- No login. The resume is plain pasted text and is not stored.
- CORS allows every origin.
- The sample postings are invented. Use `--remotive` for real ones.
- Skill extraction is a fixed word list, so it misses skills that are not on the list.
- The chat is not streamed. The answer appears when the agent has finished.
- Conversation history is kept in the browser and sent with each message. Nothing is saved on the server.

## Test results

Run on PostgreSQL 16 with pgvector 0.6, Python 3.13, 10 November 2026: 11 passed, 0 failed.

| Test | Result |
|---|---|
| test_extract_skills_finds_known_skills | passed |
| test_extract_skills_does_not_match_inside_words | passed |
| test_search_returns_closest_job_first | passed |
| test_get_job_and_unknown_job | passed |
| test_match_resume_lists_matching_skills | passed |
| test_skill_gap_splits_have_and_missing | passed |
| test_interview_prep_returns_skills_to_revise | passed |
| test_api_endpoints_work_without_an_llm_key | passed |
| test_agent_loop_calls_tool_then_answers | passed |
| test_agent_answers_directly_when_no_tool_is_needed | passed |
| test_mcp_server_exposes_the_five_tools | passed |

Also checked by hand in a real browser (Chromium): search, resume match, skill gap, and a chat turn that showed the tool call and the answer.

What was not verified when this was built:

- A real LLM. No API key was available, so the chat and the agent loop were only run with a scripted stand-in for the LLM. The first real test is yours, with your key.
- The real embedding model. The build machine could not download it, so tests and the browser check used the stand-in embedder, which matches shared words only. "Search by meaning" has not been seen working yet.
- `eval_retrieval.py` with the real model. It runs, but there is no real Recall@5 number yet.
- `--remotive`, the start scripts, the pgvector install step, and anything on macOS.
