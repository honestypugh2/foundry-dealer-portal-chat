import { useState, useEffect, type ReactNode } from 'react';
import type { AppConfig } from '../types';
import { fetchAppConfig } from '../services/api';

type View = 'chat' | 'documents' | 'search';

interface LayoutProps {
  children: ReactNode;
  activeView: View;
  onViewChange: (view: View) => void;
}

function Layout({ children, activeView, onViewChange }: LayoutProps) {
  const [config, setConfig] = useState<AppConfig | null>(null);

  useEffect(() => {
    fetchAppConfig().then(setConfig).catch(() => {});
  }, []);

  return (
    <div className="app-layout">
      <header className="app-header">
        <h1>
          JAYCO Dealer Portal
          <span className="badge">AI-Powered</span>
        </h1>
        <nav className="app-nav">
          <button
            className={activeView === 'chat' ? 'active' : ''}
            onClick={() => onViewChange('chat')}
          >
            Chat Assistant
          </button>
          <button
            className={activeView === 'search' ? 'active' : ''}
            onClick={() => onViewChange('search')}
          >
            Search
          </button>
          <button
            className={activeView === 'documents' ? 'active' : ''}
            onClick={() => onViewChange('documents')}
          >
            Documents
          </button>
        </nav>
      </header>
      {config && (
        <div className="config-bar">
          <span className={`config-mode ${config.mode}`}>
            {config.mode === 'live' ? '🟢 Live' : '🟡 Simulated'}
          </span>
          <span className="config-item">Model: {config.model_deployment}</span>
          <span className="config-item">KB: {config.kb_model}</span>
          <span className="config-item">
            {config.agentic_retrieval_enabled ? 'Agentic Retrieval' : 'Standard Search'}
          </span>
          <span className="config-item">Agent: {config.agent_service}</span>
        </div>
      )}
      <main className="app-main">
        {children}
      </main>
    </div>
  );
}

export default Layout;
