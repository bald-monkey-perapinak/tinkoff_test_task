import { Vacancy } from '../types';

interface Props {
  vacancies: Vacancy[];
  favorites: Set<string>;
  onToggleFavorite: (v: Vacancy) => void;
  onOpenUrl?: (url: string) => void;
  loading?: boolean;
}

function SkeletonCard() {
  return (
    <div className="skeleton-card">
      <div className="skel skel-title" />
      <div className="skel skel-sub" />
      <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
        {[60, 80, 55].map((w, i) => (
          <div key={i} className="skel" style={{ width: w, height: 24, borderRadius: 999 }} />
        ))}
      </div>
      <div className="skel skel-line" />
      <div className="skel skel-line-sm" />
    </div>
  );
}

function isRemote(schedule: string): boolean {
  const s = schedule.toLowerCase();
  return s.includes('удал') || s.includes('remote');
}

export function VacancyList({ vacancies, favorites, onToggleFavorite, onOpenUrl, loading }: Props) {
  if (loading) {
    return (
      <div>
        {[1, 2, 3].map(i => <SkeletonCard key={i} />)}
      </div>
    );
  }

  if (!vacancies.length) {
    return (
      <div className="empty-state">
        <span className="empty-icon">🔍</span>
        <div className="empty-title">Вакансий нет</div>
        <div className="empty-sub">Попробуйте изменить запрос или&nbsp;снять фильтры</div>
      </div>
    );
  }

  const handleOpen = (url: string) => {
    if (onOpenUrl) onOpenUrl(url);
    else window.open(url, '_blank');
  };

  return (
    <div>
      {vacancies.map((v, i) => (
        <div
          className="card"
          key={v.id}
          style={{ animationDelay: `${Math.min(i, 10) * 0.04}s` }}
        >
          {/* Top row */}
          <div className="card-top">
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="card-title">{v.title}</div>
              {v.company && (
                <div className="card-company">
                  {v.company}{v.city ? ` · ${v.city}` : ''}
                </div>
              )}
            </div>
            <button
              className={`fav-btn${favorites.has(v.id) ? ' active' : ''}`}
              onClick={() => onToggleFavorite(v)}
              title={favorites.has(v.id) ? 'Убрать из избранного' : 'В избранное'}
              aria-label="избранное"
            >
              {favorites.has(v.id) ? '★' : '☆'}
            </button>
          </div>

          {/* Pills */}
          <div className="card-pills">
            {v.salary && (
              <span className="pill salary">💰 {v.salary}</span>
            )}
            {v.schedule && (
              <span className={`pill${isRemote(v.schedule) ? ' remote' : ''}`}>
                {isRemote(v.schedule) ? '🌐 ' : ''}{v.schedule}
              </span>
            )}
            {v.experience && (
              <span className="pill">{v.experience}</span>
            )}
            {v.is_mock && (
              <span className="pill" style={{ opacity: 0.6 }}>demo</span>
            )}
          </div>

          {/* Skills */}
          {v.skills.length > 0 && (
            <div className="skills">
              {v.skills.slice(0, 8).map((s, idx) => (
                <span className="skill-chip" key={idx}>{s}</span>
              ))}
              {v.skills.length > 8 && (
                <span className="skill-chip" style={{ color: 'var(--text-3)' }}>
                  +{v.skills.length - 8}
                </span>
              )}
            </div>
          )}

          {/* CTA */}
          {v.url && (
            <button className="link-btn" onClick={() => handleOpen(v.url)}>
              Открыть на hh.ru
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <path d="M2.5 10.5l8-8M10.5 2.5H4.5M10.5 2.5v6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
