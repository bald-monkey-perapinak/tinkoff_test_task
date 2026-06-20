import { useState, useEffect, useCallback, useRef } from 'react';
import WebApp from '@twa-dev/sdk';
import { Vacancy, AnalysisResult, Criteria, Favorite, Area } from '../types';
import {
  searchVacancies, uploadFile, analyzeVacancies,
  getFavorites, addFavorite, removeFavorite,
  searchAreas, exportVacancies,
} from '../api';

export type Tab = 'search' | 'analysis' | 'upload' | 'subs';

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

function showError(msg: string) {
  try {
    WebApp.showAlert(msg);
  } catch {
    console.error(msg);
  }
}

export function useVacancyAgent() {
  const saved = loadFilters();
  const [tab, setTab] = useState<Tab>('search');
  const [query, setQuery] = useState(saved?.query ?? '');
  const [area, setArea] = useState(saved?.area ?? '');
  const [areaName, setAreaName] = useState(saved?.areaName ?? '');
  const [salaryFrom, setSalaryFrom] = useState(saved?.salaryFrom ?? '');
  const [schedule, setSchedule] = useState(saved?.schedule ?? '');
  const [experience, setExperience] = useState(saved?.experience ?? '');
  const [remoteOnly, setRemoteOnly] = useState(saved?.remoteOnly ?? false);
  const [dateFrom, setDateFrom] = useState(saved?.dateFrom ?? '');

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
    saveFilters({ query, area, areaName, salaryFrom, schedule, experience, remoteOnly, dateFrom });
  }, [query, area, areaName, salaryFrom, schedule, experience, remoteOnly, dateFrom]);

  const loadFavorites = useCallback(async () => {
    try {
      const data = await getFavorites();
      setFavList(data.favorites);
      setFavorites(new Set(data.favorites.map((f: Favorite) => f.vacancy_id)));
    } catch (err) {
      console.warn('Failed to load favorites:', err);
    }
  }, []);

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
  }, [loadFavorites]);

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

  const handleSelectArea = useCallback((a: Area) => {
    setArea(a.id);
    setAreaName(a.name);
    setAreaSuggestions([]);
    WebApp.HapticFeedback.impactOccurred('light');
  }, []);

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
      date_from: dateFrom || null,
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
  }, [query, areaName, remoteOnly, salaryFrom, experience, dateFrom, analyzing]);

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
    } catch {
      showError('Не удалось обновить избранное');
    }
  }, [favorites, loadFavorites]);

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

  const openVacancyUrl = useCallback((url: string) => {
    if (url) {
      WebApp.openLink(url);
    }
  }, []);

  return {
    tab, setTab,
    query, setQuery,
    area, areaName,
    salaryFrom, setSalaryFrom,
    schedule, setSchedule,
    experience, setExperience,
    remoteOnly, setRemoteOnly,
    dateFrom, setDateFrom,
    vacancies, total, results, report,
    favorites, favList,
    searching, analyzing, uploading,
    areaSuggestions, page, loadingMore, hasMore,
    handleSearch, handleAreaSearch, handleSelectArea,
    handleAnalyze, handleUpload, toggleFavorite,
    handleLoadMore, handleExport, openVacancyUrl,
    loadFavorites,
  };
}

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
