import { useState, useRef, useEffect } from 'react';
import type { ChatMessage } from '../types';
import { sendChatMessage } from '../services/api';
import ChatMessageBubble from './ChatMessage';

const SAMPLE_QUESTIONS = [
  'My trailer has excessive tire wear—what could be causing this and how do I fix it?',
  "I'm noticing high hub temperature and unusual noise from the wheel—what could be wrong?",
  'How do I repack the bearings step by step?',
  'What maintenance should I regularly perform on the suspension system?',
  'How do I identify whether I have a 7K or 8K beam assembly?',
];

function ChatBot() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (messageText?: string) => {
    const text = messageText || input.trim();
    if (!text || isLoading) return;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const history = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const response = await sendChatMessage({
        message: text,
        conversation_id: conversationId,
        history,
      });

      setConversationId(response.conversation_id);

      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.answer,
        citations: response.citations,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch {
      const errorMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="welcome-message">
            <h2>JAYCO Technical Support Assistant</h2>
            <p>
              Ask questions about axles, suspension, hubs, bearings, brakes, and maintenance
              procedures for JAYCO trailers.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <ChatMessageBubble key={msg.id} message={msg} />
        ))}

        {isLoading && (
          <div className="chat-message assistant">
            <div className="avatar">AI</div>
            <div className="bubble">
              <div className="loading-dots">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="sample-questions-bar">
        {SAMPLE_QUESTIONS.map((q) => (
          <button key={q} onClick={() => handleSend(q)} disabled={isLoading}>
            {q}
          </button>
        ))}
      </div>

      <div className="chat-input-container">
        <div className="chat-input-wrapper">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about JAYCO trailer maintenance..."
            disabled={isLoading}
          />
          <button onClick={() => handleSend()} disabled={!input.trim() || isLoading}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

export default ChatBot;
