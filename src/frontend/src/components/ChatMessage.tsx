import ReactMarkdown from 'react-markdown';
import type { ChatMessage } from '../types';

interface ChatMessageProps {
  message: ChatMessage;
}

function ChatMessageBubble({ message }: ChatMessageProps) {
  return (
    <div className={`chat-message ${message.role}`}>
      <div className="avatar">
        {message.role === 'user' ? 'You' : 'AI'}
      </div>
      <div className="bubble">
        <ReactMarkdown>{message.content}</ReactMarkdown>

        {message.citations && message.citations.length > 0 && (
          <div className="citations">
            <div className="citations-title">Sources ({message.citations.length})</div>
            {message.citations.map((citation, idx) => (
              <div key={idx} className="citation-item">
                {citation.blob_url ? (
                  <a
                    href={citation.blob_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="citation-link"
                  >
                    📄 {citation.document_name}
                    {citation.page_number && ` (p. ${citation.page_number})`}
                  </a>
                ) : (
                  <span>
                    📄 {citation.document_name}
                    {citation.page_number && ` (p. ${citation.page_number})`}
                  </span>
                )}
                <span
                  className={`source-badge ${citation.source_system.toLowerCase().replace(/\s+/g, '-')}`}
                >
                  {citation.source_system}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default ChatMessageBubble;
