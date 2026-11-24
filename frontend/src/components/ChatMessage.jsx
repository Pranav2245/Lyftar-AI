import React from 'react';

function ChatMessage({ message }) {
  const { content, metadata } = message;
  return (
    <div
      data-testid="assistant-message"
      style={{
        marginBottom: '0.75rem',
        padding: '0.6rem 0.8rem',
        backgroundColor: '#f1f8e9',
        borderRadius: '8px',
        border: '1px solid #c5e1a5',
      }}
    >
      <div style={{ marginBottom: '0.4rem' }}>
        <strong>Assistant:</strong> {content}
      </div>
      {metadata && (
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '0.6rem',
            fontSize: '0.78rem',
            color: '#555',
            borderTop: '1px solid #dcedc8',
            paddingTop: '0.4rem',
          }}
        >
          <span data-testid="meta-source" style={badgeStyle(metadata.resolution_source === 'LLM_CACHE' ? '#ff9800' : '#4caf50')}>
            {metadata.resolution_source}
          </span>
          <span data-testid="meta-model">{metadata.model}</span>
          <span data-testid="meta-latency">{metadata.latency_ms} ms</span>
          <span data-testid="meta-input-tokens">{metadata.input_tokens}</span>
          <span data-testid="meta-output-tokens">{metadata.output_tokens}</span>
        </div>
      )}
    </div>
  );
}

function badgeStyle(color) {
  return {
    backgroundColor: color,
    color: '#fff',
    padding: '1px 6px',
    borderRadius: '4px',
    fontWeight: 600,
  };
}

export default ChatMessage;
