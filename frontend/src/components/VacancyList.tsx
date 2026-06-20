import { Vacancy } from '../types';

interface Props {
  vacancies: Vacancy[];
  favorites: Set<string>;
  onToggleFavorite: (v: Vacancy) => void;
  onOpenUrl?: (url: string) => void;
}

export function VacancyList({ vacancies, favorites, onToggleFavorite, onOpenUrl }: Props) {
  if (!vacancies.length) {
    return (
      <div className="empty-state">
        <div className="empty-state-mark">—</div>
        <div className="empty-state-text">Нет вакансий для отображения</div>
      </div>
    );
  }

  const handleOpen = (url: string) => {
    if (onOpenUrl) {
      onOpenUrl(url);
    } else {
      window.open(url, '_blank');
    }
  };

  return (
    <div className="section">
      {vacancies.map((v, i) => (
        <div className="card" key={v.id} style={{ animationDelay: `${Math.min(i, 8) * 0.03}s` }}>
          <div className="card-header">
            <div>
              <div className="card-title">{v.title}</div>
              <div className="card-company">{v.company}</div>
            </div>
            <button
              className={`star-btn ${favorites.has(v.id) ? 'is-fav' : ''}`}
              onClick={() => onToggleFavorite(v)}
              title={favorites.has(v.id) ? 'Убрать из избранного' : 'В избранное'}
            >
              {favorites.has(v.id) ? '★' : '☆'}
            </button>
          </div>
          <div className="card-meta">
            {v.salary && (
              <span className="meta-item salary">
                <span className="meta-value">{v.salary}</span>
              </span>
            )}
            {v.city && (
              <span className="meta-item">
                <span className="meta-value">{v.city}</span>
              </span>
            )}
            {v.experience && (
              <span className="meta-item">
                <span className="meta-value">{v.experience}</span>
              </span>
            )}
            {v.schedule && (
              <span className={`badge ${v.schedule.toLowerCase().includes('удал') ? 'remote' : ''}`}>
                {v.schedule}
              </span>
            )}
          </div>
          {v.skills.length > 0 && (
            <div className="skills">
              {v.skills.map((s, idx) => (
                <span className="skill" key={idx}>
                  {s}
                </span>
              ))}
            </div>
          )}
          {v.url && (
            <button className="link-btn" onClick={() => handleOpen(v.url)}>
              Открыть на hh.ru →
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
