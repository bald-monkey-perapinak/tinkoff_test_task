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
import './App.css';

type Tab = 'search' | 'analysis' | 'upload' | 'subs';

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'search',   label: 'Поиск',    icon: '🔍' },
  { id: 'analysis', label: 'AI',       icon: '🤖' },
  { id: 'upload',   label: 'Загрузка', icon: '📁' },
  { id: 'subs',     label: 'Алерты',   icon: '🔔' },
];

const SCHEDULE_OPTIONS = [
  { value: '',          label: 'Любой формат' },
  { value: 'remote',    label: '🌐 Удалёнка' },
  { value: 'fullDay',   label: '🏢 Офис' },
  { value: 'flexible',  label: '⚡ Гибкий' },
];

const EXPERIENCE_OPTIONS = [
  { value: '',             label: 'Любой опыт' },
  { value: 'noExperience', label: 'Без опыта' },
  { value: 'between1And3', label: '1–3 года' },
  { value: 'between3And6', label: '3–6 лет' },
  { value: 'moreThan6',    label: '6+ лет' },
];

// ─── Theme / viewport ────────────────────────────────────────────────────────

function applyTelegramTheme() {
  const t = WebApp.themeParams;
  const r = document.documentElement;
  const isDark = t.bg_color
    ? parseInt(t.bg_color.replace('#', ''), 16) < 0x888888
    : true;

  r.setAttribute('data-theme', isDark ? 'dark' : 'light');

  if (t.bg_color)            r.style.setProperty('--tg-bg',   t.bg_color);
  if (t.text_color)          r.style.setProperty('--tg-text', t.text_color);
  if (t.hint_color)          r.style.setProperty('--tg-hint', t.hint_color);
  if (t.secondary_bg_color)  r.style.setProperty('--tg-s2',   t.secondary_bg_color);
}

function applyTelegramViewport() {
  const r = document.documentElement;
  r.style.setProperty('--tg-viewport-height',        `${WebApp.viewportHeight}px`);
  r.style.setProperty('--tg-viewport-stable-height', `${WebApp.viewportStableHeight}px`);
  r.style.setProperty('--tg-safe-area-inset-top',    `${(WebApp.safeAreaInset as any)?.top ?? 0}px`);
  r.style.setProperty('--tg-safe-area-inset-bottom', `${(WebApp.safeAreaInset as any)?.bottom ?? 0}px`);
}

// ─── localStorage helpers ─────────────────────────────────────────────────────

const K_FILTERS  = 'va_filters';
const K_SESSION  = 'va_session';
const K_VACANCIES = 'va_vacancies';

function ls<T>(key: string, fallback: T): T {
  try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; }
  catch { return fallback; }
}
function lsSet(key: string, val: unknown) {
  try { localStorage.setItem(key, JSON.stringify(val)); } catch {}
}

// ─── Toaster ─────────────────────────────────────────────────────────────────

function showError(msg: string) {
  try { WebApp.showAlert(msg); } catch { console.error(msg); }
}

// ─── App ─────────────────────────────────────────────────────────────────────

export default function App() {
  const saved = ls<Record<string, unknown>>(K_FILTERS, {});

  // Filters
  const [query,      setQuery]      = useState<string>(saved.query as string ?? '');
  const [area,       setArea]       = useState<string>(saved.area as string ?? '');
  const [areaName,   setAreaName]   = useState<string>(saved.areaName as string ?? '');
  const [salaryFrom, setSalaryFrom] = useState<string>(saved.salaryFrom as string ?? '');
  const [schedule,   setSchedule]   = useState<string>(saved.schedule as string ?? '');
  const [experience, setExperience] = useState<string>(saved.experience as string ?? '');
  const [remoteOnly, setRemoteOnly] = useState<boolean>(saved.remoteOnly as boolean ?? false);
  const [dateFrom,   setDateFrom]   = useState<string>(saved.dateFrom as string ?? '');

  // Data
  const [vacancies,  setVacancies]  = useState<Vacancy[]>(() => ls(K_VACANCIES, []));
  const [total,      setTotal]      = useState(0);
  const [results,    setResults]    = useState<AnalysisResult[]>([]);
  const [report,     setReport]     = useState('');
  const [favorites,  setFavorites]  = useState<Set<string>>(new Set());
  const [favList,    setFavList]    = useState<Favorite[]>([]);
  const [areaSugs,   setAreaSugs]   = useState<Area[]>([]);
  const [page,       setPage]       = useState(0);
  const [hasMore,    setHasMore]    = useState(false);

  // Loading flags
  const [searching,  setSearching]  = useState(false);
  const [analyzing,  setAnalyzing]  = useState(false);
  const [uploading,  setUploading]  = useState(false);
  const [loadingMore,setLoadingMore]= useState(false);

  // UI
  const [tab, setTab] = useState<Tab>('search');

  const sessionRef = useRef<string | null>(ls(K_SESSION, null));
  const abortRef   = useRef<AbortController | null>(null);

  // Persist filters
  useEffect(() => {
    lsSet(K_FILTERS, { query, area, areaName, salaryFrom, schedule, experience, remoteOnly, dateFrom });
  }, [query, area, areaName, salaryFrom, schedule, experience, remoteOnly, dateFrom]);

  useEffect(() => { lsSet(K_VACANCIES, vacancies); }, [vacancies]);
  useEffect(() => { if (sessionRef.current) lsSet(K_SESSION, sessionRef.current); });

  // Init Telegram
  useEffect(() => {
    WebApp.ready();
    WebApp.expand();
    applyTelegramTheme();
    applyTelegramViewport();
    WebApp.onEvent('themeChanged', applyTelegramTheme);
    WebApp.onEvent('viewportChanged', applyTelegramViewport);
    loadFavorites();
    if (vacancies.length) setTotal(vacancies.length);
    return () => {
      WebApp.offEvent('themeChanged', applyTelegramTheme);
      WebApp.offEvent('viewportChanged', applyTelegramViewport);
      abortRef.current?.abort();
    };
  }, []);

  // ── Actions ────────────────────────────────────────────────────────────────

  async function loadFavorites() {
    try {
      const data = await getFavorites();
      setFavList(data.favorites);
      setFavorites(new Set(data.favorites.map(f => f.vacancy_id)));
    } catch {}
  }

  const handleSearch = useCallback(async () => {
    if (searching) return;
    abortRef.current?.abort();
    abortRef.current = new AbortController();
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
      try { WebApp.HapticFeedback.notificationOccurred('success'); } catch {}
    } catch (err) {
      showError(`Ошибка поиска: ${err instanceof Error ? err.message : 'Неизвестная ошибка'}`);
      try { WebApp.HapticFeedback.notificationOccurred('error'); } catch {}
    }
    setSearching(false);
  }, [query, area, salaryFrom, schedule, experience, searching]);

  const handleAreaSearch = useCallback(async (q: string) => {
    setAreaName(q);
    if (!q) { setArea(''); }
    if (q.length < 2) { setAreaSugs([]); return; }
    try {
      const data = await searchAreas(q);
      setAreaSugs(data.areas);
    } catch { setAreaSugs([]); }
  }, []);

  const handleSelectArea = (a: Area) => {
    setArea(a.id);
    setAreaName(a.name);
    setAreaSugs([]);
    try { WebApp.HapticFeedback.impactOccurred('light'); } catch {}
  };

  const handleAnalyze = useCallback(async () => {
    if (analyzing) return;
    setAnalyzing(true);
    const criteria: Criteria = {
      direction: query,
      city: areaName,
      remote_only: remoteOnly,
      min_salary: salaryFrom ? parseInt(salaryFrom) : null,
      experience_level: experience,
      key_skills: [],
      date_from: dateFrom || null,
    };
    try {
      const data = await analyzeVacancies(criteria);
      setResults(data.results);
      setReport(data.report);
      try { WebApp.HapticFeedback.notificationOccurred('success'); } catch {}
    } catch (err) {
      showError(`Ошибка AI-анализа: ${err instanceof Error ? err.message : ''}`);
    }
    setAnalyzing(false);
  }, [query, areaName, remoteOnly, salaryFrom, experience, dateFrom, analyzing]);

  const handleUpload = useCallback(async (file: File) => {
    if (uploading) return;
    setUploading(true);
    try {
      const data = await uploadFile(file);
      sessionRef.current = data.session_id;
      setVacancies(data.vacancies);
      setTotal(data.loaded);
      try {
        WebApp.HapticFeedback.notificationOccurred('success');
        WebApp.showAlert(`Загружено ${data.loaded} вакансий`);
      } catch {}
    } catch (err) {
      showError(`Ошибка загрузки: ${err instanceof Error ? err.message : ''}`);
    }
    setUploading(false);
  }, [uploading]);

  const toggleFavorite = useCallback(async (v: Vacancy) => {
    const isFav = favorites.has(v.id);
    try {
      if (isFav) await removeFavorite(v.id);
      else await addFavorite({ vacancy_id: v.id, title: v.title, company: v.company, url: v.url });
      await loadFavorites();
      try { WebApp.HapticFeedback.impactOccurred('medium'); } catch {}
    } catch { showError('Не удалось обновить избранное'); }
  }, [favorites]);

  const handleLoadMore = useCallback(async () => {
    if (loadingMore) return;
    setLoadingMore(true);
    try {
      const np = page + 1;
      const data = await searchVacancies({
        query, area: area || undefined,
        salary_from: salaryFrom ? parseInt(salaryFrom) : undefined,
        schedule: schedule || undefined,
        experience: experience || undefined,
        page: np, per_page: 20,
      });
      setVacancies(prev => [...prev, ...data.vacancies]);
      setPage(np);
      setHasMore((vacancies.length + data.vacancies.length) < data.total);
    } catch (err) {
      showError(`Ошибка: ${err instanceof Error ? err.message : ''}`);
    }
    setLoadingMore(false);
  }, [query, area, salaryFrom, schedule, experience, page, loadingMore, vacancies.length]);

  const handleDownloadReport = () => {
    const blob = new Blob([report], { type: 'text/markdown' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = 'vacancy-report.md'; a.click();
    URL.revokeObjectURL(url);
  };

  const handleExport = useCallback(async (fmt: 'json' | 'csv') => {
    try {
      const blob = await exportVacancies(fmt);
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href = url; a.download = `vacancies.${fmt}`; a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      showError(`Ошибка экспорта: ${err instanceof Error ? err.message : ''}`);
    }
  }, []);

  const openUrl = (url: string) => { try { WebApp.openLink(url); } catch { window.open(url, '_blank'); }};

  // ── Render ─────────────────────────────────────────────────────────────────
  const currentFilters = {
    query, area: areaName,
    schedule,
    min_salary: salaryFrom ? parseInt(salaryFrom) : null,
  };

  return (
    <div className="app">
      {/* Header */}
      <div className="header">
        <div className="header-icon">✦</div>
        <div className="header-text">
          <div className="header-title">Карьерный агент</div>
          <div className="header-sub">
            {favList.length > 0
              ? `${favList.length} в избранном · ${vacancies.length} вакансий`
              : vacancies.length > 0
                ? `${vacancies.length} вакансий загружено`
                : 'AI-поиск на hh.ru'}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        <div className="tabs-inner">
          {TABS.map(t => (
            <button
              key={t.id}
              className={`tab${tab === t.id ? ' active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="content">

        {/* ── Search tab ──────────────────────────────────────────────── */}
        {tab === 'search' && (
          <div className="section-gap">
            {/* Query */}
            <div className="form-group">
              <label className="form-label">Должность</label>
              <input
                className="form-input"
                placeholder="Junior Python Developer"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                maxLength={200}
              />
            </div>

            {/* City */}
            <div className="form-group autocomplete-wrap">
              <label className="form-label">Город</label>
              <input
                className="form-input"
                placeholder="Любой город"
                value={areaName}
                onChange={e => handleAreaSearch(e.target.value)}
                maxLength={100}
              />
              {areaSugs.length > 0 && (
                <div className="autocomplete-pop">
                  {areaSugs.map(a => (
                    <div key={a.id} className="autocomplete-item" onClick={() => handleSelectArea(a)}>
                      {a.name}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Salary + Schedule grid */}
            <div className="form-grid">
              <div className="form-group">
                <label className="form-label">Зарплата от, ₽</label>
                <input
                  className="form-input"
                  type="number"
                  placeholder="0"
                  value={salaryFrom}
                  onChange={e => setSalaryFrom(e.target.value)}
                  min={0}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Опыт</label>
                <select
                  className="form-select"
                  value={experience}
                  onChange={e => setExperience(e.target.value)}
                >
                  {EXPERIENCE_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Schedule pills */}
            <div className="form-group">
              <label className="form-label">Формат работы</label>
              <div className="filter-pills">
                {SCHEDULE_OPTIONS.map(o => (
                  <button
                    key={o.value}
                    className={`filter-pill${schedule === o.value ? ' active' : ''}`}
                    onClick={() => setSchedule(o.value)}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Remote toggle + date */}
            <div className="form-grid">
              <label className="toggle-row">
                <span className="toggle-label">Только удалёнка</span>
                <span className="toggle">
                  <input
                    type="checkbox"
                    checked={remoteOnly}
                    onChange={e => setRemoteOnly(e.target.checked)}
                  />
                  <span className="toggle-track" />
                </span>
              </label>
              <div className="form-group">
                <label className="form-label">Дата от</label>
                <input
                  className="form-input"
                  type="date"
                  value={dateFrom}
                  onChange={e => setDateFrom(e.target.value)}
                />
              </div>
            </div>

            {/* Search button */}
            <button className="btn btn-primary" onClick={handleSearch} disabled={searching}>
              {searching ? (
                <><span className="spinner" /> Ищу вакансии…</>
              ) : '🔍 Найти вакансии'}
            </button>

            {/* Results */}
            {total > 0 && (
              <div className="count-badge">
                Найдено <strong>{total}</strong> · показано {vacancies.length}
              </div>
            )}

            <VacancyList
              vacancies={vacancies}
              favorites={favorites}
              onToggleFavorite={toggleFavorite}
              onOpenUrl={openUrl}
              loading={searching}
            />

            {hasMore && (
              <button
                className="btn btn-ghost"
                onClick={handleLoadMore}
                disabled={loadingMore}
              >
                {loadingMore ? <><span className="spinner spinner-accent" /> Загружаю…</> : 'Загрузить ещё'}
              </button>
            )}
          </div>
        )}

        {/* ── Analysis tab ─────────────────────────────────────────────── */}
        {tab === 'analysis' && (
          <div className="section-gap">
            <button
              className="btn btn-primary"
              onClick={handleAnalyze}
              disabled={analyzing || vacancies.length === 0}
            >
              {analyzing
                ? <><span className="spinner" /> AI анализирует вакансии…</>
                : vacancies.length === 0
                  ? 'Сначала найдите вакансии'
                  : `✦ Запустить AI-анализ (${vacancies.length} вакансий)`}
            </button>

            <AnalysisPanel
              results={results}
              onOpenUrl={openUrl}
              loading={analyzing}
            />

            {report && (
              <>
                <div className="divider" />
                <div className="export-row">
                  <button className="btn btn-ghost btn-sm" style={{ flex: 1 }} onClick={handleDownloadReport}>
                    ↓ .md
                  </button>
                  <button className="btn btn-ghost btn-sm" style={{ flex: 1 }} onClick={() => handleExport('csv')}>
                    ↓ .csv
                  </button>
                  <button className="btn btn-ghost btn-sm" style={{ flex: 1 }} onClick={() => handleExport('json')}>
                    ↓ .json
                  </button>
                </div>
                <div className="report-view">{report}</div>
              </>
            )}
          </div>
        )}

        {/* ── Upload tab ───────────────────────────────────────────────── */}
        {tab === 'upload' && (
          <div className="section-gap">
            <FileUpload onFileSelect={handleUpload} isLoading={uploading} />
            {vacancies.length > 0 && (
              <>
                <div className="count-badge">
                  Загружено: <strong>{vacancies.length}</strong> вакансий
                </div>
                <VacancyList
                  vacancies={vacancies}
                  favorites={favorites}
                  onToggleFavorite={toggleFavorite}
                  onOpenUrl={openUrl}
                />
              </>
            )}
          </div>
        )}

        {/* ── Subscriptions tab ────────────────────────────────────────── */}
        {tab === 'subs' && (
          <SubscriptionsTab currentFilters={currentFilters} />
        )}
      </div>
    </div>
  );
}
