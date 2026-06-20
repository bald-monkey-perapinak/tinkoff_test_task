import { AgentMetadata, AnalysisResult } from '../types';

interface Props {
  results: AnalysisResult[];
  metadata?: AgentMetadata | null;
  onOpenUrl?: (url: string) => void;
  loading?: boolean;
}

const RANK_EMOJI = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣'];

function scoreColor(score: number): string {
  if (score >= 8) return 'var(--green)';
  if (score >= 5) return 'var(--yellow)';
  return 'var(--red)';
}

function ScoreRing({ score }: { score: number }) {
  const r = 24;
  const stroke = 4.5;
  const circ = 2 * Math.PI * r;
  const fill = (score / 10) * circ;
  const color = scoreColor(score);
  const size = (r + stroke) * 2 + 4;

  return (
    <svg
      className="score-ring-wrap"
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      aria-label={`Оценка ${score} из 10`}
    >
      {/* Track */}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="rgba(255,255,255,0.07)"
        strokeWidth={stroke}
      />
      {/* Fill */}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={`${fill} ${circ}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{
          transition: 'stroke-dasharray 0.85s cubic-bezier(0.4,0,0.2,1)',
          filter: `drop-shadow(0 0 4px ${color}80)`,
        }}
      />
      {/* Score number */}
      <text
        x={size / 2}
        y={size / 2 + 1}
        textAnchor="middle"
        dominantBaseline="middle"
        fill={color}
        fontSize="15"
        fontWeight="700"
        fontFamily="Inter, sans-serif"
      >
        {score}
      </text>
    </svg>
  );
}

function SkeletonCard() {
  return (
    <div className="skeleton-card">
      <div className="skel skel-title" />
      <div className="skel skel-sub" />
      <div style={{ display: 'flex', gap: 14, margin: '12px 0' }}>
        <div className="skel" style={{ width: 58, height: 58, borderRadius: '50%' }} />
        <div style={{ flex: 1 }}>
          <div className="skel" style={{ height: 13, width: '60%', marginBottom: 6 }} />
          <div className="skel" style={{ height: 13, width: '40%' }} />
        </div>
      </div>
      <div className="skel skel-line" />
    </div>
  );
}

export function AnalysisPanel({ results, metadata, onOpenUrl, loading }: Props) {
  if (loading) {
    return <div>{[1,2,3].map(i => <SkeletonCard key={i}/>)}</div>;
  }

  if (!results.length) {
    return (
      <div className="empty-state">
        <span className="empty-icon">🤖</span>
        <div className="empty-title">AI-анализ ещё не запущен</div>
        <div className="empty-sub">
          Нажмите кнопку выше — агент изучит вакансии,<br />
          расставит их по приоритетам и объяснит почему
        </div>
      </div>
    );
  }

  const handleOpen = (url: string) => {
    if (onOpenUrl) onOpenUrl(url);
    else window.open(url, '_blank');
  };

  return (
    <div>
      <div className="count-badge" style={{ marginBottom: 12 }}>
        <strong>Топ-{results.length}</strong> по версии AI
      </div>
      {metadata && (
        <div className="agent-meta">
          <div className="agent-meta-title">{metadata.plan_goal || 'Агентный анализ вакансий'}</div>
          <div className="agent-meta-row">
            <span>{metadata.analysis_type}</span>
            <span>{metadata.iterations_used} ит.</span>
            <span>{metadata.total_vacancies_pool} в пуле</span>
            <span>{metadata.total_searches ?? 0} поисков</span>
            <span>{metadata.reflections_count ?? 0} рефлексий</span>
          </div>
          {metadata.overall_summary && <div className="agent-meta-summary">{metadata.overall_summary}</div>}
        </div>
      )}

      {results.map((r, i) => {
        const v = r.vacancy;
        return (
          <div
            className="card"
            key={r.vacancy_id}
            style={{ animationDelay: `${Math.min(i, 8) * 0.06}s` }}
          >
            {/* Header */}
            <div className="card-top">
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 4 }}>
                  <span style={{ fontSize: 18 }}>{RANK_EMOJI[i] ?? `${i+1}.`}</span>
                  <span
                    className="pill"
                    style={{
                      background: 'var(--accent-soft)',
                      color: 'var(--accent)',
                      border: 'none',
                      fontSize: 11,
                    }}
                  >
                    #{r.rank} место
                  </span>
                </div>
                <div className="card-title">{r.summary}</div>
                {v && (
                  <div className="card-company">
                    {v.company}{v.city ? ` · ${v.city}` : ''}
                  </div>
                )}
              </div>
            </div>

            {/* Score ring */}
            <div className="score-row">
              <ScoreRing score={r.fit_score} />
              <div className="score-info">
                <div className="score-rank">Соответствие</div>
                <div className="score-label" style={{ fontWeight: 600, color: scoreColor(r.fit_score) }}>
                  {r.fit_score} / 10
                </div>
                {r.recommendation && (
                  <div className="score-label" style={{ marginTop: 4, fontSize: 12 }}>
                    {r.recommendation}
                  </div>
                )}
              </div>
            </div>

            {/* Why / Concerns */}
            {r.why_fits && (
              <div className="explain-block why">
                <div className="explain-title">✓ Почему подходит</div>
                {r.why_fits}
              </div>
            )}
            {r.concerns && (
              <div className="explain-block concern">
                <div className="explain-title">⚠ Что смущает</div>
                {r.concerns}
              </div>
            )}

            {/* Open link */}
            {v?.url && (
              <div style={{ marginTop: 12 }}>
                <button className="link-btn" onClick={() => handleOpen(v.url)}>
                  Открыть вакансию
                  <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                    <path d="M2.5 10.5l8-8M10.5 2.5H4.5M10.5 2.5v6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
