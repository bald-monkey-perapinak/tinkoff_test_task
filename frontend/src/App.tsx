import { useState, useEffect, useCallback, useRef } from 'react';
import WebApp from '@twa-dev/sdk';
import { Vacancy, AnalysisResult, Criteria, Favorite, Area } from './types';
import {
  searchVacancies, uploadFile, analyzeVacancies,
  getFavorites, addFavorite, removeFavorite,
  searchAreas, exportVacancies,
} from './api';
import { VacancyList } from './components/VacancyList';
import { AnalysisPanel } from './components/AnalysisPanel';
import { FileUpload } from './components/FileUpload';
import { SubscriptionsTab } from './components/SubscriptionsTab';

type Tab = 'search' | 'analysis' | 'upload' | 'subs';

const SCHEDULE_OPTIONS = [
  { value: '', label: 'Любой формат' },
  { value: 'remote', label: 'Удалёнка' },
  { value: 'fullDay', label: 'Полный день' },
  { value: 'flexible', label: 'Гибкий' },
];

const EXPERIENCE_OPTIONS = [
  { value: '', label: 'Любой опыт' },
  { value: 'noExperience', label: 'Без опыта' },
  { value: 'between1And3', label: '1–3 года' },
  { value: 'between3And6', label: '3–6 лет' },
];

function applyTelegramTheme() {
  const theme = WebApp.themeParams;
  const root = document.documentElement;
  if (theme.bg_color) root.style.setProperty('--bg', theme.bg_color);
  if (theme.text_color) root.style.setProperty('--text', theme.text_color);
  if (theme.button_color) root.style.setProperty('--primary', theme.button_color);
  if (theme.button_text_color) root.style.setProperty('--primary-text', theme.button_text_color);
  if (theme.secondary_bg_color) root.style.setProperty('--card-bg', theme.secondary_bg_color);
  if (theme.hint_color) root.style.setProperty('--border', theme.hint_color);
  if (theme.link_color) root.style.setProperty('--link', theme.link_color);
}

function applyTelegramViewport() {
  const root = document.documentElement;
  root.style.setProperty('--tg-viewport-height', `${WebApp.viewportHeight}px`);
  root.style.setProperty('--tg-viewport-stable-height', `${WebApp.viewportStableHeight}px`);
  root.style.setProperty('--tg-safe-area-inset-top', `${WebApp.safeAreaInset?.top ?? 0}px`);
  root.style.setProperty('--tg-safe-area-inset-bottom', `${WebApp.safeAreaInset?.bottom ?? 0}px`);
}

function showError(msg: string) {
  try {
    WebApp.showAlert(msg);
  } catch {
    console.error(msg);
  }
}

const STORAGE_KEY = 'vacancy_agent_filters';

function loadFilters() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return null;
}

function saveFilters(filters: Record<string, unknown>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
  } catch {}
}

export default function App() {
  const saved = loadFilters();
  const [tab, setTab] = useState<Tab>('search');
  const [query, setQuery] = useState(saved?.query ?? '');
  const [area, setArea] = useState(saved?.area ?? '');
  const [areaName, setAreaName] = useState(saved?.areaName ?? '');
  const [salaryFrom, setSalaryFrom] = useState(saved?.salaryFrom ?? '');
  const [schedule, setSchedule] = useState(saved?.schedule ?? '');
  const [experience, setExperience] = useState(saved?.experience ?? '');
  const [remoteOnly, setRemoteOnly] = useState(saved?.remoteOnly ?? false);

  const [vacancies, setVacancies] = useState<Vacancy[]>([]);
  const [total, setTotal] = useState(0);
  const [results, setResults] = useState<AnalysisResult[]>([]);
  const [report, setReport] = useState('');
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [favList, setFavList] = useState<Favorite[]>([]);

  const [searching, setSearching] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [areaSuggestions, setAreaSuggestions] = useState<Area[]>([]);
  const [page, setPage] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);

  const sessionIdRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    saveFilters({ query, area, areaName, salaryFrom, schedule, experience, remoteOnly });
  }, [query, area, areaName, salaryFrom, schedule, experience, remoteOnly]);

  useEffect(() => {
    WebApp.ready();
    WebApp.expand();
    applyTelegramTheme();
    applyTelegramViewport();

    WebApp.onEvent('themeChanged', applyTelegramTheme);
    WebApp.onEvent('viewportChanged', applyTelegramViewport);

    loadFavorites();

    return () => {
      WebApp.offEvent('themeChanged', applyTelegramTheme);
      WebApp.offEvent('viewportChanged', applyTelegramViewport);
      abortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    WebApp.MainButton.hide();
    WebApp.BackButton.hide();

    if (tab === 'search' && vacancies.length > 0) {
      WebApp.MainButton.setText('AI-проанализировать');
      WebApp.MainButton.show();
      WebApp.MainButton.onClick(handleAnalyze);
    }

    if (tab === 'analysis' && results.length > 0) {
      WebApp.BackButton.show();
      WebApp.BackButton.onClick(() => setTab('search'));
    }

    if (tab === 'upload') {
      WebApp.MainButton.setText('Загрузить файл');
      WebApp.MainButton.show();
      WebApp.MainButton.onClick(() => {
        const input = document.querySelector<HTMLInputElement>('input[type="file"]');
        input?.click();
      });
    }

    return () => {
      WebApp.MainButton.offClick(() => {});
      WebApp.BackButton.offClick(() => {});
    };
  }, [tab, vacancies, results]);

  async function loadFavorites() {
    try {
      const data = await getFavorites();
      setFavList(data.favorites);
      setFavorites(new Set(data.favorites.map((f) => f.vacancy_id)));
    } catch (err) {
      console.warn('Failed to load favorites:', err);
    }
  }

  const handleSearch = useCallback(async () => {
    if (searching) return;
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    WebApp.MainButton.showProgress();
    setSearching(true);
    setResults([]);
    setReport('');
    setPage(0);
    try {
      const data = await searchVacancies({
        query,
        area: area || undefined,
        salary_from: salaryFrom ? parseInt(salaryFrom) : undefined,
        schedule: schedule || undefined,
        experience: experience || undefined,
        per_page: 20,
      });
      setVacancies(data.vacancies);
      setTotal(data.total);
      setHasMore(data.vacancies.length < data.total);
      WebApp.HapticFeedback.notificationOccurred('success');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Неизвестная ошибка';
      showError(`Ошибка поиска: ${msg}`);
      WebApp.HapticFeedback.notificationOccurred('error');
    }
    setSearching(false);
    WebApp.MainButton.hideProgress();
  }, [query, area, salaryFrom, schedule, experience, searching]);

  const handleAreaSearch = useCallback(async (q: string) => {
    setAreaName(q);
    if (q.length < 2) {
      setAreaSuggestions([]);
      return;
    }
    try {
      const data = await searchAreas(q);
      setAreaSuggestions(data.areas);
    } catch {
      setAreaSuggestions([]);
    }
  }, []);

  const handleSelectArea = (a: Area) => {
    setArea(a.id);
    setAreaName(a.name);
    setAreaSuggestions([]);
    WebApp.HapticFeedback.impactOccurred('light');
  };

  const handleAnalyze = useCallback(async () => {
    if (analyzing) return;
    WebApp.MainButton.showProgress();
    setAnalyzing(true);
    WebApp.MainButton.setText('AI анализирует...');
    const criteria: Criteria = {
      direction: query,
      city: areaName,
      remote_only: remoteOnly,
      min_salary: salaryFrom ? parseInt(salaryFrom) : null,
      experience_level: experience,
      key_skills: [],
    };
    try {
      const data = await analyzeVacancies(criteria);
      setResults(data.results);
      setReport(data.report);
      WebApp.HapticFeedback.notificationOccurred('success');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Неизвестная ошибка';
      showError(`Ошибка AI-анализа: ${msg}`);
      WebApp.HapticFeedback.notificationOccurred('error');
    }
    setAnalyzing(false);
    WebApp.MainButton.hideProgress();
    WebApp.MainButton.setText('AI-проанализировать');
  }, [query, areaName, remoteOnly, salaryFrom, experience, analyzing]);

  const handleUpload = useCallback(async (file: File) => {
    if (uploading) return;
    setUploading(true);
    WebApp.MainButton.showProgress();
    try {
      const data = await uploadFile(file);
      sessionIdRef.current = data.session_id;
      setVacancies(data.vacancies);
      setTotal(data.loaded);
      WebApp.HapticFeedback.notificationOccurred('success');
      WebApp.showAlert(`Загружено ${data.loaded} вакансий`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Неизвестная ошибка';
      showError(`Ошибка загрузки: ${msg}`);
      WebApp.HapticFeedback.notificationOccurred('error');
    }
    setUploading(false);
    WebApp.MainButton.hideProgress();
  }, [uploading]);

  const toggleFavorite = useCallback(async (v: Vacancy) => {
    const isFav = favorites.has(v.id);
    try {
      if (isFav) {
        await removeFavorite(v.id);
      } else {
        await addFavorite({ vacancy_id: v.id, title: v.title, company: v.company, url: v.url });
      }
      await loadFavorites();
      WebApp.HapticFeedback.impactOccurred('medium');
    } catch (err) {
      showError('Не удалось обновить избранное');
    }
  }, [favorites]);

  const handleDownloadReport = () => {
    const blob = new Blob([report], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'vacancy-report.md';
    a.click();
    URL.revokeObjectURL(url);
    WebApp.HapticFeedback.impactOccurred('light');
  };

  const handleLoadMore = useCallback(async () => {
    if (loadingMore) return;
    setLoadingMore(true);
    try {
      const nextPage = page + 1;
      const data = await searchVacancies({
        query,
        area: area || undefined,
        salary_from: salaryFrom ? parseInt(salaryFrom) : undefined,
        schedule: schedule || undefined,
        experience: experience || undefined,
        page: nextPage,
        per_page: 20,
      });
      setVacancies((prev) => [...prev, ...data.vacancies]);
      setPage(nextPage);
      setHasMore((vacancies.length + data.vacancies.length) < data.total);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Неизвестная ошибка';
      showError(`Ошибка загрузки: ${msg}`);
    }
    setLoadingMore(false);
  }, [query, area, salaryFrom, schedule, experience, page, loadingMore, vacancies.length]);

  const handleExport = useCallback(async (format: 'json' | 'csv') => {
    try {
      const blob = await exportVacancies(format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `vacancy-export.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      WebApp.HapticFeedback.impactOccurred('light');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Неизвестная ошибка';
      showError(`Ошибка экспорта: ${msg}`);
    }
  }, []);

  const openVacancyUrl = (url: string) => {
    if (url) {
      WebApp.openLink(url);
    }
  };

  const currentFilters = { query, area: areaName, schedule, min_salary: salaryFrom ? parseInt(salaryFrom) : null };

  return (
    <div className="app" style={{ paddingTop: 'var(--tg-safe-area-inset-top)' }}>
      <div className="tabs">
        <button className={`tab ${tab === 'search' ? 'active' : ''}`} onClick={() => setTab('search')}>
          Поиск
        </button>
        <button className={`tab ${tab === 'analysis' ? 'active' : ''}`} onClick={() => setTab('analysis')}>
          AI-анализ
        </button>
        <button className={`tab ${tab === 'upload' ? 'active' : ''}`} onClick={() => setTab('upload')}>
          Загрузка
        </button>
        <button className={`tab ${tab === 'subs' ? 'active' : ''}`} onClick={() => setTab('subs')}>
          Уведомления
        </button>
      </div>

      {tab === 'search' && (
        <>
          <div className="search-form">
            <input
              className="input"
              placeholder="Должность, например «junior python developer»"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              maxLength={200}
            />
            <div style={{ position: 'relative' }}>
              <input
                className="input"
                placeholder="Город"
                value={areaName}
                onChange={(e) => handleAreaSearch(e.target.value)}
                maxLength={100}
              />
              {areaSuggestions.length > 0 && (
                <div style={{
                  position: 'absolute', top: '100%', left: 0, right: 0,
                  background: 'var(--card-bg)', border: '1px solid var(--border)',
                  borderRadius: 8, zIndex: 10, maxHeight: 200, overflowY: 'auto',
                }}>
                  {areaSuggestions.map((a) => (
                    <div
                      key={a.id}
                      onClick={() => handleSelectArea(a)}
                      style={{ padding: '8px 12px', cursor: 'pointer', fontSize: 13 }}
                    >
                      {a.name}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="filters-row">
              <input
                className="input"
                type="number"
                placeholder="Зарплата от"
                value={salaryFrom}
                onChange={(e) => setSalaryFrom(e.target.value)}
                min={0}
                max={10000000}
              />
              <select className="select" value={schedule} onChange={(e) => setSchedule(e.target.value)}>
                {SCHEDULE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div className="filters-row">
              <select className="select" value={experience} onChange={(e) => setExperience(e.target.value)}>
                {EXPERIENCE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
              <label className="checkbox-row">
                <input type="checkbox" checked={remoteOnly} onChange={(e) => setRemoteOnly(e.target.checked)} />
                Только удалёнка
              </label>
            </div>
            <button className="btn btn-primary" onClick={handleSearch} disabled={searching}>
              {searching ? 'Поиск...' : 'Найти вакансии'}
            </button>
          </div>
          {total > 0 && <div className="total-badge">Найдено: {total} вакансий, показаны первые {vacancies.length}</div>}
          <VacancyList
            vacancies={vacancies}
            favorites={favorites}
            onToggleFavorite={toggleFavorite}
            onOpenUrl={openVacancyUrl}
          />
          {hasMore && (
            <button
              className="btn btn-outline"
              onClick={handleLoadMore}
              disabled={loadingMore}
              style={{ width: '100%', marginTop: 12 }}
            >
              {loadingMore ? 'Загрузка...' : 'Загрузить ещё'}
            </button>
          )}
        </>
      )}

      {tab === 'analysis' && (
        <>
          <button className="btn btn-primary" onClick={handleAnalyze} disabled={analyzing} style={{ width: '100%', marginBottom: 12 }}>
            {analyzing ? 'AI анализирует...' : 'AI-проанализировать вакансии'}
          </button>
          <AnalysisPanel results={results} onOpenUrl={openVacancyUrl} />
          {report && (
            <>
              <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                <button className="btn btn-outline" onClick={handleDownloadReport} style={{ flex: 1 }}>
                  Скачать .md
                </button>
                <button className="btn btn-outline" onClick={() => handleExport('csv')} style={{ flex: 1 }}>
                  Скачать .csv
                </button>
                <button className="btn btn-outline" onClick={() => handleExport('json')} style={{ flex: 1 }}>
                  Скачать .json
                </button>
              </div>
              <div className="report-view">{report}</div>
            </>
          )}
        </>
      )}

      {tab === 'upload' && (
        <>
          <FileUpload onFileSelect={handleUpload} isLoading={uploading} />
          {vacancies.length > 0 && (
            <>
              <div className="total-badge">Загружено: {vacancies.length} вакансий</div>
              <VacancyList
                vacancies={vacancies}
                favorites={favorites}
                onToggleFavorite={toggleFavorite}
                onOpenUrl={openVacancyUrl}
              />
            </>
          )}
        </>
      )}

      {tab === 'subs' && (
        <SubscriptionsTab currentFilters={currentFilters} />
      )}
    </div>
  );
}
