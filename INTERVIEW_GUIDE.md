# InternInsider interview guide

Read this with `backend/app/tools.py` and `backend/app/agent.py` open. Those two files are the project.

## The 30-second pitch

"InternInsider is a career copilot. You paste a resume and it finds matching job postings, shows your skill gaps for a job, and prepares interview questions. Postings are stored in PostgreSQL with pgvector, so search works on meaning, not keywords. On top of that there's a LangGraph agent: an LLM that decides which of five tools to call. The same five tools are also exposed through an MCP server, so other AI apps can use them."

## Before the interview: CV versus this code

Check this list against the CV, because the interviewer will ask about the specific words and numbers on it.

| CV says | In this code |
|---|---|
| React + FastAPI + PostgreSQL app | Yes |
| LangGraph LLM agent with 5 tools | Yes: `agent.py`, `tools.py` |
| Exposed via MCP | Yes: `mcp_server.py`, tested |
| Job matching, skill-gap analysis, interview prep | Yes, one or more tools each |
| pgvector embedding retrieval | Yes |
| Grounded in real job postings | The sample data is invented. `python -m app.ingest --remotive` loads real ones. Run it before you say "real". |
| Raised Recall@5 by 22% | Not measured here. `eval_retrieval.py` measures Recall@5 for keyword vs pgvector. Run it and quote the number you get, with the dataset size. |
| Fine-tuned DistilBERT on 3,500 postings, macro-F1 0.62 to 0.78 | Not in this code. Skill extraction here is a word list. There is no classifier and no fine-tuning. |

If the DistilBERT work exists somewhere else, have it ready to show. If it doesn't, don't present those numbers as measured results. An interviewer who asks "how did you split train and test?" or "what were the classes?" will find out in two questions, and that costs more than saying "that part is planned; what's built is the agent and the retrieval".

## Concepts, one at a time

### Embeddings

An embedding model turns a piece of text into a list of numbers, here 384 of them. Texts with similar meaning get similar lists. "Making apps for phones" and "iOS Developer, Swift" share no words, but their vectors point in nearly the same direction.

`embed()` in `db.py` does this with a small open model, `BAAI/bge-small-en-v1.5`, running locally through the `fastembed` library. Why local: no API key for search, no cost per query, and the resume text never leaves the machine for the search part.

### pgvector

pgvector is a PostgreSQL extension that adds a `vector` column type and distance operators. Each job row stores its embedding. To search, embed the query and ask Postgres for the nearest rows:

```sql
ORDER BY embedding <=> $query_vector LIMIT 5
```

`<=>` is cosine distance: 0 means same direction, bigger means less similar. Similarity shown in the UI is `1 - distance`.

The HNSW index makes this fast on large tables. It is approximate: it finds very close neighbours quickly but may occasionally miss the true nearest one. Without an index Postgres does an exact scan of every row, which is fine for a few thousand jobs.

### Why keyword search isn't enough

Keyword search (Postgres full-text, `tsvector`) only matches shared words. A student types "work with data" and the posting says "pandas, SQL, predictive models". Embeddings catch that. Keyword search is still better for exact terms like a company name, which is why real systems often combine both (hybrid search).

### Tool calling

An LLM only produces text. Tool calling is a convention: you give the model a list of functions (name, description, argument types). When it wants one, it replies with structured JSON like `{"name": "skill_gap", "args": {"job_id": 5, ...}}` instead of prose. Your code runs the function and sends the result back as another message. The model never touches the database. It only asks.

That is why the docstrings in `tools.py` matter: they are the descriptions the model reads to choose a tool.

### LangGraph and the agent loop

An agent is an LLM in a loop with tools. LangGraph lets you write that loop as a graph. Ours has two nodes:

```
START -> agent --(asked for a tool)--> tools --> back to agent
           |
           +--(wrote a normal answer)--> END
```

- `agent` node: sends the messages to the LLM and appends its reply.
- `tools` node: runs the function the LLM asked for and appends the result.
- `tools_condition`: looks at the last message. Tool call: go to `tools`. Otherwise: end.

The state is just the list of messages. One question can take several trips round the loop: "what am I missing for the best job for me?" needs `match_resume` and then `skill_gap`.

`recursion_limit=12` stops a confused model from looping forever.

### The five tools

| Tool | What it does | Uses the LLM? |
|---|---|---|
| `search_jobs(query)` | pgvector search | no |
| `get_job(job_id)` | one posting in full | no |
| `match_resume(resume_text)` | embeds the resume, finds nearest jobs, lists overlapping skills | no |
| `skill_gap(resume_text, job_id)` | set difference between job skills and resume skills | no |
| `interview_prep(job_id)` | returns the skills and posting; the LLM writes the questions from it | no |

All five are deterministic Python and SQL. The LLM decides which to call and words the answer. So the facts (which jobs exist, which skills are missing) come from the database, and the model can't make them up. That is what "grounded" means.

### MCP

MCP (Model Context Protocol) is a standard for how an AI app discovers and calls tools on a server. `mcp_server.py` registers the same five functions. An MCP client such as Claude Desktop starts the script, asks "what tools do you have?", and can then call them.

LangGraph vs MCP: LangGraph is how my own agent uses the tools. MCP is how someone else's agent can use them without me writing an integration for each app.

### How the frontend and backend connect

`api.ts` has one `request()` helper that calls `fetch("http://localhost:8001" + path)`. The React dev server is on port 5174 and the API on 8001, so the backend has CORS middleware to allow it. The backend keeps no chat state: the browser sends the earlier messages with each request.

## Request lifecycle: "What am I missing for job 5?"

1. React: `handleSend` calls `sendChat(message, resume, history)`.
2. Browser: `POST /api/chat` with the message, the resume text, and earlier messages.
3. FastAPI validates the body against `ChatRequest` and calls `run_agent`.
4. `run_agent` builds the message list: system prompt (with the resume), history, the new message.
5. Graph, `agent` node: the LLM gets the messages and the five tool descriptions. It replies with a tool call: `skill_gap(resume_text=..., job_id=5)`.
6. `tools_condition` sees the tool call and routes to the `tools` node.
7. `tools` node runs `skill_gap`: reads job 5 from Postgres, extracts skills from the resume, compares the two sets, returns have / missing / percent.
8. Back to the `agent` node. The LLM now sees the tool result and writes a normal answer.
9. `tools_condition` sees no tool call. The graph ends.
10. FastAPI returns `{reply, tool_calls}`. React shows the answer with the tool line above it.

## Why this, and why not that

**LangGraph, not a plain while-loop or LangChain's old AgentExecutor.** A hand-written loop works for one tool cycle. LangGraph makes the control flow explicit and inspectable, and adding a step (a human-approval node, a retry, a second agent) is adding a node. I kept the graph to two nodes on purpose.

**pgvector, not Pinecone or Chroma.** The job data already lives in Postgres. Keeping vectors in the same table means one database, one query that can filter by location and rank by similarity together, and no syncing between two stores. A dedicated vector database makes sense at hundreds of millions of vectors.

**Local embedding model, not the OpenAI embeddings API.** Free, no rate limits, search works with no key. The trade-off is quality: a 384-dimension small model is weaker than a large hosted one.

**Tools as plain functions.** One implementation, three callers (agent, MCP, REST). Easy to unit test without an LLM.

**Word-list skill extraction, not a model.** Transparent and testable. It misses skills not on the list and gets fooled by ambiguous words ("go"). An NER or classifier model would be the next step, and it would need labelled data.

**Deterministic tools, LLM only for choosing and wording.** Keeps facts out of the model's hands, keeps cost down (one or two LLM calls per question), and makes the logic testable.

**FastAPI.** Type-hint validation, automatic docs at `/docs`, and it's what the Python AI libraries are easiest to use from.

## A real bug from building it

The skill extractor first had short aliases, "js" for javascript and "ts" for typescript. A posting that mentioned "Next.js" came back with JavaScript as a required skill, because "js" matched after the dot. So the skill gap told a candidate they were missing a skill the job never asked for. The fix was to remove the two-letter aliases and add a test that "java" isn't found inside "javascript" and "go" isn't found inside "google". The lesson: substring matching on short tokens produces false positives, and in this app a false positive is shown to the user as career advice.

## How it's tested

11 tests, all runnable with no API key and no network.

- Skill extraction: known skills found, no matches inside other words.
- Tools: run against a real Postgres with pgvector, using a simple stand-in embedder. Checks nearest-first ordering, the skill gap sets, unknown ids.
- API: each endpoint, and that chat returns a clear 503 with no key.
- Agent: the real graph with a scripted fake LLM that says "call search_jobs" and then gives an answer. The test checks the tool really ran against the database and its output was shown to the LLM on the second turn.
- MCP: starts the server as a subprocess, lists the tools, calls one.

Why a fake LLM: a real one costs money, is slow, and gives different text every run. The fake tests my code (the loop and the wiring). It does not test whether the real model picks the right tool. For that you need an evaluation set of questions with the expected tool, run against the real model.

## Scaling

Say what it is first: a single-process demo, tried with 24 postings.

1. **LLM calls** are the slow and expensive part: seconds each, and the endpoint blocks while it waits. Fixes: stream the answer, make the endpoint async, cache repeated questions, use a small model for tool choice.
2. **Embedding at ingest** is one posting at a time. Batch it, and run it as a background job.
3. **Vector search**: the HNSW index handles millions of rows. Add a `WHERE` filter on location or category so the index searches less.
4. **Database connections**: every tool call opens a new connection. Use a connection pool.
5. **The resume is sent to the LLM in every request.** Summarise it once, or store its extracted skills.
6. **Chat state** is in the browser. For multiple devices, store conversations in Postgres (LangGraph has a checkpointer for this).

## Limits to name yourself

- An LLM can still choose the wrong tool or misread a result. The tools limit what it can get wrong, they don't remove it.
- The skill list is fixed and English-only.
- No evaluation of answer quality yet, only retrieval.
- No auth, and resumes are personal data. A real version needs login, storage rules, and a note that the resume is sent to OpenAI.

## Likely questions, short answers

**What is an agent?** An LLM in a loop that can call tools and decides for itself when to stop.

**How does the LLM know which tool to use?** It is sent each tool's name, docstring and argument types. It picks from that description.

**What stops hallucinated jobs?** Jobs only come from tool results, which come from the database. The system prompt forbids inventing postings, and answers cite job ids you can check.

**Cosine similarity or Euclidean distance?** Cosine compares direction and ignores length, which suits text embeddings. For normalised vectors the two give the same ranking.

**What is Recall@5?** Of the postings that are relevant to a query, the share that appear in the top 5 results.

**Why HNSW and not IVFFlat?** HNSW has better recall at the same speed and needs no training step. IVFFlat builds faster and uses less memory.

**What is RAG, and is this RAG?** Retrieval-augmented generation: fetch relevant text, give it to the LLM, let it answer from that. Yes. The retrieval step here is a tool the agent chooses to call.

**Why MCP if you already have a REST API?** REST is for my frontend. MCP is the standard AI apps already speak, so they can discover and call the tools with no custom code.

**How did you build it, did you use AI?** Answer truthfully. Saying you used an AI assistant and then showing you understand each file is a fine answer. Claiming otherwise falls apart on follow-up questions.

## Tonight, in this order

1. Get it running (README setup), then add your OpenAI key and ask the chat three questions.
2. Read `tools.py`, then `agent.py`. Together they are about 165 lines.
3. Run `python eval_retrieval.py` and write down the two Recall@5 numbers.
4. Run `python -m pytest -v`.
5. Say the request lifecycle out loud without looking.
6. Go through the CV table at the top of this guide and decide what you will say for each row.
