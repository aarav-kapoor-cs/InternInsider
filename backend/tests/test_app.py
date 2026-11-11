import asyncio
import sys

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage

from app import tools
from app.agent import build_agent, run_agent
from app.skills import extract_skills

RESUME = "Second-year CS student. Projects in Python and FastAPI with PostgreSQL. Comfortable with Docker and Git."


# ------------------------------------------------------------------ skills

def test_extract_skills_finds_known_skills():
    assert extract_skills("I use Python, postgres and React Native") == ["postgresql", "python", "react", "react native"]


def test_extract_skills_does_not_match_inside_words():
    # "java" must not be found inside "javascript", "go" not inside "google"
    assert extract_skills("JavaScript at Google") == ["javascript"]


# ------------------------------------------------------------------- tools

def test_search_returns_closest_job_first():
    results = tools.search_jobs("Kotlin Android Jetpack Compose transit app", limit=3)
    assert len(results) == 3
    assert results[0]["title"] == "Android Developer"
    # nearest first: similarity never increases down the list
    assert [r["similarity"] for r in results] == sorted((r["similarity"] for r in results), reverse=True)


def test_get_job_and_unknown_job():
    assert tools.get_job(1)["company"] == "Lumen Labs"
    assert "error" in tools.get_job(9999)


def test_match_resume_lists_matching_skills():
    results = tools.match_resume(RESUME)
    top = results[0]
    assert top["title"] == "Backend Engineer Intern"
    assert {"python", "fastapi", "postgresql", "docker"} <= set(top["matching_skills"])


def test_skill_gap_splits_have_and_missing():
    gap = tools.skill_gap(RESUME, job_id=5)  # Backend Engineer Intern
    assert gap["have"] == ["docker", "fastapi", "postgresql", "python"]
    assert gap["missing"] == ["pytest", "rest", "sql"]
    assert gap["match_percent"] == 57


def test_interview_prep_returns_skills_to_revise():
    prep = tools.interview_prep(9)  # Machine Learning Intern
    assert "pytorch" in prep["skills_to_revise"]
    assert prep["title"] == "Machine Learning Intern"


# --------------------------------------------------------------------- API

def test_api_endpoints_work_without_an_llm_key():
    with TestClient(__import__("app.main").main.app) as client:
        assert client.get("/api/health").json() == {"jobs": 24, "llm_configured": False}
        assert client.get("/api/jobs/search", params={"q": "Swift iOS"}).json()[0]["title"] == "iOS Developer Intern"
        assert len(client.get("/api/jobs").json()) == 24
        assert client.post("/api/skills", json={"text": RESUME}).json() == ["docker", "fastapi", "git", "postgresql", "python"]
        assert client.get("/api/jobs/9999").status_code == 404
        assert client.post("/api/match", json={"resume_text": RESUME}).status_code == 200
        assert client.post("/api/skill-gap", json={"resume_text": RESUME, "job_id": 5}).json()["match_percent"] == 57
        # chat needs a key: a clear 503, not a crash
        assert client.post("/api/chat", json={"message": "hi"}).status_code == 503


# ------------------------------------------------------------------- agent

class ScriptedLLM:
    """
    TEST ONLY. Stands in for the real LLM so the graph can be tested with no
    API key. It replays a fixed list of replies, one per call.
    """

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen_tools = []

    def bind_tools(self, tools):
        self.seen_tools = [t.__name__ for t in tools]
        return self

    def invoke(self, messages):
        self.last_messages = messages
        return self.replies.pop(0)


def test_agent_loop_calls_tool_then_answers():
    llm = ScriptedLLM([
        # 1st LLM turn: "call search_jobs"
        AIMessage(content="", tool_calls=[{"name": "search_jobs", "args": {"query": "Swift iOS", "limit": 2}, "id": "call_1"}]),
        # 2nd LLM turn: a normal answer, which ends the loop
        AIMessage(content="Job 17, iOS Developer Intern at Trailmark, fits best."),
    ])
    agent = build_agent(llm)
    result = run_agent(agent, "Find me iOS jobs", resume_text=RESUME)

    assert llm.seen_tools == ["search_jobs", "get_job", "match_resume", "skill_gap", "interview_prep"]
    assert result["tool_calls"] == [{"name": "search_jobs", "args": {"query": "Swift iOS", "limit": 2}}]
    assert result["reply"].startswith("Job 17")
    # On its 2nd turn the LLM was shown the real tool output from PostgreSQL.
    tool_message = llm.last_messages[-1]
    assert isinstance(tool_message, ToolMessage)
    assert "iOS Developer Intern" in tool_message.content
    # The resume was placed in the system prompt.
    assert RESUME in llm.last_messages[0].content


def test_agent_answers_directly_when_no_tool_is_needed():
    agent = build_agent(ScriptedLLM([AIMessage(content="Hello! Paste your resume to start.")]))
    result = run_agent(agent, "hi")
    assert result == {"reply": "Hello! Paste your resume to start.", "tool_calls": []}


# --------------------------------------------------------------------- MCP

def test_mcp_server_exposes_the_five_tools():
    """Start the MCP server as a real subprocess and talk to it like an AI app would."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def scenario():
        params = StdioServerParameters(command=sys.executable, args=["-m", "app.mcp_server"])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = [t.name for t in (await session.list_tools()).tools]
                result = await session.call_tool("skill_gap", {"resume_text": RESUME, "job_id": 5})
                return names, result

    names, result = asyncio.run(scenario())
    assert names == ["search_jobs", "get_job", "match_resume", "skill_gap", "interview_prep"]
    assert not result.is_error
    assert '"match_percent"' in result.content[0].text and "57" in result.content[0].text
