import React, { useState, useEffect } from 'react';
import ChatMessage from './components/ChatMessage';

const API_BASE = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

function App() {
  const [sessionId, setSessionId] = useState('');
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');

  // Generate a new session on mount
  useEffect(() => {
    const id = 's-' + Math.random().toString(36).substring(2, 12);
    setSessionId(id);
  }, []);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    const userMsg = { role: 'user', content: trimmed };
    const newMsgs = [...messages, userMsg];
    setMessages(newMsgs);
    setInput('');
    setLoading(true);
    setError('');

    try {
      const payload = { session_id: sessionId, message: trimmed };
      if (systemPrompt.trim()) {
        payload.system_prompt = systemPrompt.trim();
      }

      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Error ${res.status}`);
      }

      const data = await res.json();
      const assistantMsg = {
        role: 'assistant',
        content: data.reply,
        metadata: data.metadata,
      };
      setMessages([...newMsgs, assistantMsg]);
    } catch (e) {
      setError(e.message || 'Unexpected error');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div style={styles.container}>
      <h1 style={styles.title}>💬 Lyftr AI</h1>

      {/* Optional system prompt */}
      <input
        data-testid="system-prompt-input"
        type="text"
        placeholder="System prompt (optional)"
        value={systemPrompt}
        onChange={(e) => setSystemPrompt(e.target.value)}
        style={styles.systemInput}
      />

      {/* Chat area */}
      <div style={styles.chatArea}>
        {messages.map((msg, idx) =>
          msg.role === 'assistant' ? (
            <ChatMessage key={idx} message={msg} />
          ) : (
            <div key={idx} style={styles.userBubble}>
              <strong>You:</strong> {msg.content}
            </div>
          )
        )}
        {loading && <p style={styles.loading}>⏳ Thinking...</p>}
        {error && <p style={styles.error}>⚠️ {error}</p>}
      </div>

      {/* Input area */}
      <div style={styles.inputRow}>
        <textarea
          data-testid="chat-input"
          rows={2}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message..."
          style={styles.textarea}
        />
        <button
          data-testid="send-button"
          onClick={handleSend}
          disabled={loading}
          style={styles.button}
        >
          Send
        </button>
      </div>
    </div>
  );
}

const styles = {
  container: {
    maxWidth: '700px',
    margin: '2rem auto',
    padding: '1rem',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  title: { textAlign: 'center', marginBottom: '0.5rem' },
  systemInput: {
    width: '100%',
    padding: '0.5rem',
    marginBottom: '0.75rem',
    border: '1px solid #ccc',
    borderRadius: '6px',
    fontSize: '0.9rem',
    boxSizing: 'border-box',
  },
  chatArea: {
    minHeight: '400px',
    maxHeight: '60vh',
    overflowY: 'auto',
    border: '1px solid #ddd',
    borderRadius: '8px',
    padding: '1rem',
    backgroundColor: '#fafafa',
    marginBottom: '1rem',
  },
  userBubble: {
    marginBottom: '0.75rem',
    padding: '0.6rem 0.8rem',
    backgroundColor: '#e3f2fd',
    borderRadius: '8px',
  },
  inputRow: { display: 'flex', gap: '0.5rem', alignItems: 'flex-end' },
  textarea: {
    flex: 1,
    padding: '0.5rem',
    fontSize: '1rem',
    borderRadius: '6px',
    border: '1px solid #ccc',
    resize: 'none',
  },
  button: {
    padding: '0.5rem 1.5rem',
    fontSize: '1rem',
    borderRadius: '6px',
    border: 'none',
    backgroundColor: '#1976d2',
    color: '#fff',
    cursor: 'pointer',
  },
  loading: { color: '#888' },
  error: { color: 'red' },
};

export default App;
