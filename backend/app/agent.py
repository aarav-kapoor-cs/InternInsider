"""
The LangGraph agent.

An "agent" is an LLM in a loop that can call tools. The graph has two nodes:

    START -> agent --(LLM asked for a tool)--> tools --+
               ^                                        |
               +----------------------------------------+
               |
               +--(LLM wrote a normal answer)--> END

  agent node: send the conversation to the LLM. It replies EITHER with a final
              answer OR with "please call tool X with these arguments".
  tools node: run the requested Python function and append its result to the
              conversation. Then go back to the agent node.
The loop ends when the LLM answers without asking for a tool.
"""
import os

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.tools import ALL_TOOLS

# "provider:model". Change it in backend/.env without touching the code.
DEFAULT_MODEL = "openai:gpt-5.4-mini"

SYSTEM_PROMPT = """You are InternInsider, a career copilot for students looking for internships.
You can search real job postings, match a resume to jobs, find skill gaps, and prepare interview questions.
Rules:
- Always use the tools to look up jobs. Never invent a job posting, company, or job id.
- When you mention a job, include its id, title and company.
- If a tool needs the resume and none was provided, ask the user to paste it.
- Keep answers short and practical. Write plain text, no markdown symbols."""


def build_agent(llm=None):
    """Build and compile the graph. Tests pass in a fake `llm`."""
    llm = llm or init_chat_model(os.environ.get("LLM_MODEL", DEFAULT_MODEL))
    # bind_tools sends each tool's name, docstring and argument types to the LLM.
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    def call_model(state: MessagesState):
        reply = llm_with_tools.invoke(state["messages"])
        return {"messages": [reply]}  # appended to the conversation

    graph = StateGraph(MessagesState)  # the state is just the list of messages
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(ALL_TOOLS))
    graph.add_edge(START, "agent")
    # tools_condition looks at the LLM's last message: tool call -> "tools", else -> END
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile()


def run_agent(agent, message: str, resume_text: str = "", history: list[dict] | None = None) -> dict:
    """Run one user turn. Returns the answer and which tools the agent called."""
    system = SYSTEM_PROMPT
    if resume_text.strip():
        system += "\n\nThe user's resume:\n" + resume_text.strip()

    messages = [SystemMessage(system)]
    for item in history or []:  # earlier turns, so follow-up questions make sense
        cls = HumanMessage if item["role"] == "user" else AIMessage
        messages.append(cls(item["content"]))
    messages.append(HumanMessage(message))

    # recursion_limit stops a confused LLM from looping on tools forever.
    result = agent.invoke({"messages": messages}, {"recursion_limit": 12})

    new_messages = result["messages"][len(messages):]
    tool_calls = [
        {"name": call["name"], "args": _shorten(call["args"])}
        for m in new_messages if isinstance(m, AIMessage)
        for call in m.tool_calls
    ]
    return {"reply": result["messages"][-1].text, "tool_calls": tool_calls}


def _shorten(args: dict) -> dict:
    """Trim long arguments (like a whole resume) so the UI can show them."""
    return {k: (v[:60] + "...") if isinstance(v, str) and len(v) > 60 else v for k, v in args.items()}
