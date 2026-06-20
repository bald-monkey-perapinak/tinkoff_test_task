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
        <div className="empty-icon">🔍</div>
        <div>Нет вакансий для отображения</div>
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
      {vacancies.map((v) => (
        <div className="card" key={v.id}>
          <div className="card-header">
            <div>
              <div className="card-title">{v.title}</div>
              <div className="card-company">{v.company}</div>
            </div>
            <button
              className="star-btn"
              onClick={() => onToggleFavorite(v)}
              title={favorites.has(v.id) ? 'Убрать из избранного' : 'В избранное'}
            >
              {favorites.has(v.id) ? '★' : '☆'}
            </button>
          </div>
          <div className="card-meta">
            {v.salary && <span className="badge salary">{v.salary}</span>}
            {v.city && <span className="badge city">{v.city}</span>}
            {v.schedule && <span className="badge remote">{v.schedule}</span>}
            {v.experience && <span className="badge">{v.experience}</span>}
          </div>
          {v.skills.length > 0 && (
            <div className="skills">
              {v.skills.map((s, i) => (
                <span className="skill" key={i}>{s}</span>
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
