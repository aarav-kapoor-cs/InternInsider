import { useEffect, useRef, useState } from "react";
import { Bot, Send, Sparkles, Wrench } from "lucide-react";
import { ChatMessage } from "../api";

const SUGGESTIONS = [
  "Which jobs fit my resume best?",
  "What am I missing for my best match, and what should I learn first?",
  "Give me interview questions for my top match",
  "Find internships where I'd work with data",
];

type Props = {
  messages: ChatMessage[];
  busy: boolean;
  error: string;
  onAsk: (text: string) => void;
  llmReady: boolean;
  onClear: () => void;
};

export default function CopilotPage({ messages, busy, error, onAsk, llmReady, onClear }: Props) {
  const [input, setInput] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  // Scroll down to the newest message.
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy]);

  return (
    <div className="copilot">
      <div className="copilot-head">
        <div>
          <h1>Copilot</h1>
          <p className="lead">A LangGraph agent that chooses between five tools. Each answer shows which tools it used.</p>
        </div>
        {messages.length > 0 && <button className="btn btn-ghost" onClick={onClear}>New chat</button>}
      </div>
      {!llmReady && <div className="notice warn">Put <code>OPENAI_API_KEY=…</code> in <code>backend/.env</code> and restart the backend to turn on the copilot.</div>}

      <div className="thread">
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="chat-empty-icon"><Sparkles size={22} /></div>
            <h3>Ask about jobs, skill gaps or interview prep</h3>
            <div className="suggestions">
              {SUGGESTIONS.map((text) => <button key={text} className="suggestion" onClick={() => onAsk(text)}>{text}</button>)}
            </div>
          </div>
        )}

        {messages.map((message, i) => message.role === "user" ? (
          <div key={i} className="msg user"><div className="bubble">{message.content}</div></div>
        ) : (
          <div key={i} className="msg assistant">
            <div className="avatar"><Bot size={16} /></div>
            <div className="msg-body">
              <div className="tools-used">
                {message.tool_calls && message.tool_calls.length > 0 && <Wrench size={13} />}
                {message.tool_calls?.map((call, j) => (
                  <span key={j} className="tool" title={JSON.stringify(call.args)}>{call.name}</span>
                ))}
                {message.tokens && <span className="tokens">{(message.tokens.prompt + message.tokens.completion).toLocaleString()} tokens</span>}
              </div>
              <div className="bubble">{message.content}</div>
            </div>
          </div>
        ))}

        {busy && <div className="msg assistant"><div className="avatar"><Bot size={16} /></div><div className="bubble typing"><i /><i /><i /></div></div>}
        {error && <div className="notice bad">{error}</div>}
        <div ref={bottom} />
      </div>

      <form className="composer" onSubmit={(e) => { e.preventDefault(); onAsk(input); setInput(""); }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about jobs, skill gaps or interview prep" disabled={busy} />
        <button className="send" type="submit" disabled={busy || !input.trim()} aria-label="Send"><Send size={16} /></button>
      </form>
    </div>
  );
}
