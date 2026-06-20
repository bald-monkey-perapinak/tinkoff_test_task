import { AnalysisResult } from '../types';

interface Props {
  results: AnalysisResult[];
  onOpenUrl?: (url: string) => void;
}

function scoreClass(score: number): string {
  if (score >= 8) return 'score-high';
  if (score >= 5) return 'score-mid';
  return 'score-low';
}

function getRankLabel(rank: number): string {
  if (rank === 1) return 'Лучшее совпадение';
  if (rank === 2) return '2-е место';
  if (rank === 3) return '3-е место';
  return `${rank}-е место`;
}

export function AnalysisPanel({ results, onOpenUrl }: Props) {
  if (!results.length) {
    return (
      <div className="empty-state">
        <div className="empty-state-mark">AI</div>
        <div className="empty-state-text">Загрузите вакансии и запустите анализ — здесь появится ранжированный список</div>
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
      {results.map((r, i) => {
        const v = r.vacancy;
        return (
          <div className="card" key={r.vacancy_id} style={{ animationDelay: `${Math.min(i, 8) * 0.04}s` }}>
            <div className="card-header">
              <div>
                <div className="card-title">{r.summary}</div>
                {v && (
                  <div className="card-company">
                    {v.company} · {v.city || '—'}
                  </div>
                )}
              </div>
            </div>

            <div className="stamp-row">
              <div className={`stamp ${scoreClass(r.fit_score)}`}>{r.fit_score}/10</div>
              <div>
                <div className="stamp-rank">{getRankLabel(r.rank)}</div>
                <div className="stamp-label">соответствие критериям</div>
              </div>
            </div>

            <div className="explanation">
              <div className="explanation-label">Почему подходит</div>
              {r.why_fits}
            </div>
            {r.concerns && (
              <div className="explanation concern">
                <div className="explanation-label">Что смущает</div>
                {r.concerns}
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
