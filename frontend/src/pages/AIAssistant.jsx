import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { Alert, Badge, Button } from "../components/ui";

const SUGGESTIONS = [
  "What were our most recent deployment failures?",
  "Why did my last deployment fail?",
  "Does a timeout issue look like anything we've seen before?",
  "Which past fixes were actually confirmed to work?",
];

export default function AIAssistant() {
  const { projectId } = useAuth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef(null);

  useEffect(() => { setMessages([]); }, [projectId]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);

  const send = async (text) => {
    const message = (text ?? input).trim();
    if (!message || loading) return;
    setError("");
    setInput("");
    const history = messages.map(({ role, content }) => ({ role, content }));
    setMessages((m) => [...m, { role: "user", content: message }]);
    setLoading(true);
    try {
      const res = await api.chat({ project_id: projectId, message, history });
      setMessages((m) => [...m, { role: "assistant", content: res.reply, refs: res.references, usedMemory: res.used_memory, memoryStatus: res.memory_status }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="page-head">
        <h1>AI assistant</h1>
        <span className="muted">Ask about past failures. Answers draw on this project's stored incidents and memory.</span>
      </div>
      <div className="card">
        <div className="chat">
          {messages.length === 0 && (
            <div>
              <p className="muted">Try asking:</p>
              <div className="chips">{SUGGESTIONS.map((s) => <button key={s} type="button" className="chip" onClick={() => send(s)}>{s}</button>)}</div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              {m.content}
              {m.role === "assistant" && (
                <div className="small" style={{ marginTop: 8 }}>
                  {m.memoryStatus === "unavailable" && <div className="muted">Memory service unavailable for this answer.</div>}
                  {m.usedMemory && <div className="muted">Used recalled project memory.</div>}
                  {m.refs?.length > 0 && (
                    <div style={{ marginTop: 4 }}>
                      Referenced: {m.refs.map((r) => <span key={r.id} style={{ marginRight: 10 }}><Link to={`/incidents/${r.id}`}>Incident #{r.id}</Link> <Badge value={r.status} /></span>)}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
          {loading && <div className="msg assistant muted">Thinking…</div>}
          <div ref={endRef} />
        </div>
        <Alert>{error}</Alert>
        <form onSubmit={(e) => { e.preventDefault(); send(); }} className="row" style={{ marginTop: 12, flexWrap: "nowrap" }}>
          <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about a deployment failure…" maxLength={4000} aria-label="Message" />
          <div style={{ flex: "none", minWidth: 0 }}><Button loading={loading} type="submit">Send</Button></div>
        </form>
      </div>
    </>
  );
}
