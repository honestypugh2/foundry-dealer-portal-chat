export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  timestamp: Date;
}

export interface Citation {
  document_name: string;
  page_number: number | null;
  chunk_text: string;
  relevance_score: number;
  reranker_score: number | null;
  source_system: string;
  blob_url: string | null;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
  history: { role: string; content: string }[];
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  conversation_id: string;
  confidence_score: number;
}

export interface SearchRequest {
  query: string;
  top_k?: number;
  source_filter?: string;
}

export interface SearchResult {
  document_name: string;
  chunk_text: string;
  page_number: number | null;
  relevance_score: number;
  reranker_score: number | null;
  source_system: string;
  metadata: Record<string, unknown>;
}

export interface SearchResponse {
  results: SearchResult[];
  total_count: number;
  query: string;
}

export interface DocumentInfo {
  name: string;
  source_system: string;
  size_bytes: number | null;
  page_count: number | null;
  last_modified: string | null;
  tags: string[];
}

export interface DocumentListResponse {
  documents: DocumentInfo[];
  total_count: number;
}

export interface AppConfig {
  mode: string;
  agent_service: string;
  agentic_retrieval_enabled: boolean;
  model_deployment: string;
  kb_model: string;
  search_index: string;
  max_citations: number;
}
