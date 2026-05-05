import { useState } from 'react';
import type { SearchResult } from '../types';
import { searchDocuments } from '../services/api';

function SearchPanel() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);

    try {
      const response = await searchDocuments({ query: query.trim(), top_k: 10 });
      setResults(response.results);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <div className="search-panel">
      <h2 style={{ marginBottom: '1rem' }}>Document Search</h2>

      <div className="search-bar">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search JAYCO technical documents..."
        />
        <button onClick={handleSearch} disabled={loading}>
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>

      <div className="search-results">
        {searched && results.length === 0 && !loading && (
          <p style={{ textAlign: 'center', color: '#718096' }}>
            No results found for "{query}"
          </p>
        )}

        {results.map((result, idx) => (
          <div key={idx} className="search-result-card">
            <div className="result-header">
              <span className="result-doc">
                {result.document_name}
                {result.page_number && ` — Page ${result.page_number}`}
              </span>
              <span className="result-score">
                {result.reranker_score != null
                  ? `${(result.reranker_score / 4 * 100).toFixed(0)}% match`
                  : `${(result.relevance_score * 100).toFixed(0)}% match`}
              </span>
            </div>
            <p className="result-text">{result.chunk_text}</p>
            <div style={{ marginTop: '0.5rem' }}>
              <span
                className={`source-badge ${result.source_system.toLowerCase()}`}
                style={{
                  fontSize: '0.7rem',
                  padding: '0.15rem 0.5rem',
                  borderRadius: '3px',
                  fontWeight: 600,
                  background:
                    result.source_system === 'SharePoint' ? '#ebf8ff' : '#f0fff4',
                  color:
                    result.source_system === 'SharePoint' ? '#2b6cb0' : '#276749',
                }}
              >
                {result.source_system}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default SearchPanel;
