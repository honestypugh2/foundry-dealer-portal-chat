import { useState, useEffect } from 'react';
import type { DocumentInfo } from '../types';
import { listDocuments } from '../services/api';

function DocumentList() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    const fetchDocs = async () => {
      setLoading(true);
      try {
        const response = await listDocuments(filter);
        setDocuments(response.documents);
      } catch {
        setDocuments([]);
      } finally {
        setLoading(false);
      }
    };
    fetchDocs();
  }, [filter]);

  const formatBytes = (bytes: number | null) => {
    if (!bytes) return null;
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="documents-panel">
      <h2>Document Library ({documents.length} documents)</h2>

      <div style={{ marginBottom: '1rem', display: 'flex', gap: '0.5rem' }}>
        {['all', 'sharepoint', 'revver'].map((src) => (
          <button
            key={src}
            onClick={() => setFilter(src)}
            className={`app-nav ${filter === src ? 'active' : ''}`}
            style={{
              background: filter === src ? 'var(--company-blue)' : 'white',
              color: filter === src ? 'white' : 'var(--company-text)',
              border: '1px solid var(--company-border)',
              padding: '0.4rem 1rem',
              borderRadius: 'var(--radius)',
              cursor: 'pointer',
              fontSize: '0.85rem',
              textTransform: 'capitalize',
            }}
          >
            {src === 'all' ? 'All Sources' : src}
          </button>
        ))}
      </div>

      {loading ? (
        <p>Loading documents...</p>
      ) : (
        <div className="documents-grid">
          {documents.map((doc) => (
            <div key={doc.name} className="document-card">
              <div className="doc-name">
                <a
                  href={`/api/documents/${encodeURIComponent(doc.name)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Open document"
                  style={{ color: 'var(--company-blue-light)', textDecoration: 'none' }}
                >
                  {doc.name}
                </a>
              </div>
              <div className="doc-meta">
                <span>📁 {doc.source_system}</span>
                {doc.page_count && <span>📄 {doc.page_count} pages</span>}
                {formatBytes(doc.size_bytes) && <span>💾 {formatBytes(doc.size_bytes)}</span>}
              </div>
              <div className="doc-actions" style={{ marginTop: '0.5rem' }}>
                <a
                  href={`/api/documents/${encodeURIComponent(doc.name)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    fontSize: '0.75rem',
                    color: 'var(--company-blue-light)',
                    textDecoration: 'none',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.25rem',
                  }}
                >
                  📥 View PDF
                </a>
              </div>
              {doc.tags.length > 0 && (
                <div className="doc-tags">
                  {doc.tags.map((tag) => (
                    <span key={tag}>{tag}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default DocumentList;
