import WebApp from '@twa-dev/sdk';
import { Vacancy, AnalysisResult, Criteria, Favorite, Subscription, SearchResult, Area } from './types';

const BASE = import.meta.env.VITE_API_URL || '';
const DEFAULT_TIMEOUT = 15000;
const MAX_RETRIES = 2;

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function getTelegramInitData(): string {
  try {
    return WebApp.initData || '';
  } catch {
    return '';
  }
}

function getAuthHeaders(): Record<string, string> {
  const initData = getTelegramInitData();
  const headers: Record<string, string> = {};
  if (initData) {
    headers['Telegram-Init-Data'] = initData;
  }
  return headers;
}

async function request<T>(path: string, options: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT): Promise<T> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const resp = await fetch(`${BASE}${path}`, {
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders(), ...options.headers },
        ...options,
        signal: controller.signal,
      });
      clearTimeout(timer);

      if (!resp.ok) {
        if (resp.status === 429) {
          const retryAfter = parseInt(resp.headers.get('Retry-After') || '3', 10);
          if (attempt < MAX_RETRIES) {
            await sleep(retryAfter * 1000);
            continue;
          }
        }
        const error = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(error.detail || `HTTP ${resp.status}`);
      }
      return resp.json();
    } catch (err) {
      clearTimeout(timer);
      if (err instanceof DOMException && err.name === 'AbortError') {
        lastError = new Error('Запрос превысил время ожидания');
      } else {
        lastError = err instanceof Error ? err : new Error(String(err));
      }
      if (attempt < MAX_RETRIES) {
        await sleep(1000 * (attempt + 1));
      }
    }
  }
  throw lastError || new Error('Request failed');
}

export async function searchVacancies(params: {
  query?: string;
  area?: string;
  salary_from?: number;
  salary_to?: number;
  experience?: string;
  schedule?: string;
  professional_role?: string;
  page?: number;
  per_page?: number;
}): Promise<SearchResult> {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') sp.set(k, String(v));
  });
  return request(`/api/search?${sp.toString()}`);
}

export async function uploadFile(file: File): Promise<{ loaded: number; session_id: string; vacancies: Vacancy[] }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000);
  try {
    const formData = new FormData();
    formData.append('file', file);
    const resp = await fetch(`${BASE}/api/upload`, {
      method: 'POST',
      body: formData,
      headers: getAuthHeaders(),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!resp.ok) {
      const error = await resp.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(error.detail || `HTTP ${resp.status}`);
    }
    return resp.json();
  } catch (err) {
    clearTimeout(timer);
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Загрузка превысила время ожидания (30с)');
    }
    throw err;
  }
}

export async function analyzeVacancies(criteria: Criteria): Promise<{ results: AnalysisResult[]; report: string }> {
  return request('/api/analyze', {
    method: 'POST',
    body: JSON.stringify(criteria),
  }, 30000);
}

export async function getFavorites(): Promise<{ favorites: Favorite[] }> {
  return request('/api/favorites');
}

export async function addFavorite(fav: Favorite): Promise<void> {
  await request('/api/favorites', { method: 'POST', body: JSON.stringify(fav) });
}

export async function removeFavorite(vacancyId: string): Promise<void> {
  await request(`/api/favorites/${encodeURIComponent(vacancyId)}`, { method: 'DELETE' });
}

export async function getSubscriptions(): Promise<{ subscriptions: Subscription[] }> {
  return request('/api/subscriptions');
}

export async function createSubscription(sub: Omit<Subscription, 'id'>): Promise<{ id: number }> {
  return request('/api/subscribe', { method: 'POST', body: JSON.stringify(sub) });
}

export async function deleteSubscription(id: number): Promise<void> {
  await request(`/api/subscribe/${id}`, { method: 'DELETE' });
}

export async function searchAreas(q: string): Promise<{ areas: Area[] }> {
  return request(`/api/areas?q=${encodeURIComponent(q)}`);
}

export async function searchRoles(q: string): Promise<{ roles: Area[] }> {
  return request(`/api/roles?q=${encodeURIComponent(q)}`);
}

export async function exportVacancies(format: 'json' | 'csv'): Promise<Blob> {
  const resp = await fetch(`${BASE}/api/export?format=${format}`, {
    headers: getAuthHeaders(),
  });
  if (!resp.ok) {
    const error = await resp.json().catch(() => ({ detail: 'Export failed' }));
    throw new Error(error.detail || `HTTP ${resp.status}`);
  }
  return resp.blob();
}
