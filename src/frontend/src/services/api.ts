import type {
  ChatRequest,
  ChatResponse,
  SearchRequest,
  SearchResponse,
  DocumentListResponse,
  AppConfig,
} from '../types';

const API_BASE = '/api';

export async function fetchAppConfig(): Promise<AppConfig> {
  const response = await fetch(`${API_BASE}/config`);
  if (!response.ok) {
    throw new Error(`Config request failed: ${response.statusText}`);
  }
  return response.json();
}

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.statusText}`);
  }

  return response.json();
}

export async function searchDocuments(request: SearchRequest): Promise<SearchResponse> {
  const response = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Search request failed: ${response.statusText}`);
  }

  return response.json();
}

export async function listDocuments(source: string = 'all'): Promise<DocumentListResponse> {
  const response = await fetch(`${API_BASE}/documents?source=${encodeURIComponent(source)}`);

  if (!response.ok) {
    throw new Error(`Document list request failed: ${response.statusText}`);
  }

  return response.json();
}
