import WebApp from '@twa-dev/sdk';
import { Vacancy, Area } from '../types';
import { VacancyList } from './VacancyList';

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

interface Props {
  query: string;
  setQuery: (v: string) => void;
  areaName: string;
  salaryFrom: string;
  setSalaryFrom: (v: string) => void;
  schedule: string;
  setSchedule: (v: string) => void;
  experience: string;
  setExperience: (v: string) => void;
  remoteOnly: boolean;
  setRemoteOnly: (v: boolean) => void;
  dateFrom: string;
  setDateFrom: (v: string) => void;
  vacancies: Vacancy[];
  total: number;
  favorites: Set<string>;
  searching: boolean;
  areaSuggestions: Area[];
  loadingMore: boolean;
  hasMore: boolean;
  onSearch: () => void;
  onAreaSearch: (q: string) => void;
  onSelectArea: (a: Area) => void;
  onToggleFavorite: (v: Vacancy) => void;
  onLoadMore: () => void;
  onOpenUrl: (url: string) => void;
}

export function SearchTab({
  query, setQuery, areaName, salaryFrom, setSalaryFrom,
  schedule, setSchedule, experience, setExperience,
  remoteOnly, setRemoteOnly, dateFrom, setDateFrom,
  vacancies, total, favorites, searching, areaSuggestions,
  loadingMore, hasMore,
  onSearch, onAreaSearch, onSelectArea, onToggleFavorite,
  onLoadMore, onOpenUrl,
}: Props) {
  return (
    <>
      <div className="search-form">
        <input
          className="input"
          placeholder="Должность, например «junior python developer»"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSearch()}
          maxLength={200}
        />
        <div style={{ position: 'relative' }}>
          <input
            className="input"
            placeholder="Город"
            value={areaName}
            onChange={(e) => onAreaSearch(e.target.value)}
            maxLength={100}
          />
          {areaSuggestions.length > 0 && (
            <div style={{
              position: 'absolute', top: '100%', left: 0, right: 0,
              background: 'rgba(255,255,255,0.08)',
              backdropFilter: 'blur(20px)',
              WebkitBackdropFilter: 'blur(20px)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 12, zIndex: 10, maxHeight: 200, overflowY: 'auto',
              boxShadow: '0 8px 32px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.08)',
            }}>
              {areaSuggestions.map((a) => (
                <div
                  key={a.id}
                  onClick={() => onSelectArea(a)}
                  style={{
                    padding: '10px 14px', cursor: 'pointer', fontSize: 13,
                    borderBottom: '1px solid rgba(255,255,255,0.06)',
                    transition: 'background 0.2s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(168,85,247,0.1)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
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
        <input
          className="input"
          type="date"
          placeholder="Дата публикации от"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
        />
        <button className="btn btn-primary" onClick={onSearch} disabled={searching}>
          {searching ? 'Поиск...' : 'Найти вакансии'}
        </button>
      </div>
      {total > 0 && <div className="total-badge">Найдено: {total} вакансий, показаны первые {vacancies.length}</div>}
      <VacancyList
        vacancies={vacancies}
        favorites={favorites}
        onToggleFavorite={onToggleFavorite}
        onOpenUrl={onOpenUrl}
      />
      {hasMore && (
        <button
          className="btn btn-outline"
          onClick={onLoadMore}
          disabled={loadingMore}
          style={{ width: '100%', marginTop: 12 }}
        >
          {loadingMore ? 'Загрузка...' : 'Загрузить ещё'}
        </button>
      )}
    </>
  );
}
