import { AnalysisResult } from '../types';

interface Props {
  results: AnalysisResult[];
  onOpenUrl?: (url: string) => void;
}

function getScoreColor(score: number): string {
  if (score >= 8) return '#4caf50';
  if (score >= 6) return '#ff9800';
  if (score >= 4) return '#ff5722';
  return '#f44336';
}

function getMedal(rank: number): string {
  if (rank === 1) return '🥇';
  if (rank === 2) return '🥈';
  if (rank === 3) return '🥉';
  return `#${rank}`;
}

export function AnalysisPanel({ results, onOpenUrl }: Props) {
  if (!results.length) {
    return (
      <div className="empty-state">
        <div className="empty-icon">🤖</div>
        <div>Загрузите вакансии и нажмите «AI-анализ»</div>
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
      <div className="total-badge">Топ-{results.length} по версии AI</div>
      {results.map((r) => {
        const v = r.vacancy;
        const color = getScoreColor(r.fit_score);
        return (
          <div className="card" key={r.vacancy_id}>
            <div className="card-header">
              <div className="card-title">
                {getMedal(r.rank)} {r.summary}
              </div>
            </div>
            {v && (
              <div className="card-company">
                {v.company} · {v.city} · {v.salary || 'зарплата не указана'}
              </div>
            )}
            <div className="fit-bar">
              <span className="fit-label">Соответствие</span>
              <span className="fit-score" style={{ color }}>{r.fit_score}/10</span>
              <div className="fit-bar-track">
                <div
                  className="fit-bar-fill"
                  style={{ width: `${r.fit_score * 10}%`, background: color }}
                />
              </div>
            </div>
            <div className="explanation">
              <div className="explanation-label">Почему подходит</div>
              {r.why_fits}
            </div>
            {r.concerns && (
              <div className="explanation">
                <div className="explanation-label">Что смущает</div>
                {r.concerns}
              </div>
            )}
            {r.recommendation && (
              <div className="explanation" style={{ borderColor: 'rgba(168, 85, 247, 0.3)' }}>
                <div className="explanation-label">Рекомендация</div>
                {r.recommendation}
              </div>
            )}
            {v?.url && (
              <button className="link-btn" onClick={() => handleOpen(v.url)}>
                Открыть вакансию →
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
