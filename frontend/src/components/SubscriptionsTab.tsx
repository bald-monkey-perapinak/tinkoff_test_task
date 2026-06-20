import { useState, useEffect } from 'react';
import WebApp from '@twa-dev/sdk';
import { Subscription } from '../types';
import { getSubscriptions, deleteSubscription, createSubscription } from '../api';

interface Props {
  currentFilters: {
    query: string;
    area: string;
    schedule: string;
    min_salary: number | null;
  };
}

function getChatId(): number {
  try {
    const user = (WebApp as any).initDataUnsafe?.user;
    if (user?.id) return user.id;
  } catch {}
  return 0;
}

function formatFilters(s: Subscription): string {
  return [
    s.area,
    s.schedule,
    s.min_salary ? `от ${s.min_salary.toLocaleString('ru')} ₽` : null,
  ].filter(Boolean).join(' · ') || 'Без фильтров';
}

export function SubscriptionsTab({ currentFilters }: Props) {
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState('');

  useEffect(() => { loadSubs(); }, []);

  async function loadSubs() {
    setLoading(true);
    setError('');
    try {
      const data = await getSubscriptions();
      setSubs(data.subscriptions);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки');
    }
    setLoading(false);
  }

  async function handleCreate() {
    const chatId = getChatId();
    if (!chatId) {
      setError('Не удалось определить Telegram ID. Откройте приложение в Telegram.');
      return;
    }
    setCreating(true);
    try {
      await createSubscription({
        chat_id: chatId,
        query: currentFilters.query,
        area: currentFilters.area || null,
        schedule: currentFilters.schedule || null,
        min_salary: currentFilters.min_salary || null,
        is_active: true,
      });
      await loadSubs();
      try { WebApp.HapticFeedback.notificationOccurred('success'); } catch {}
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка создания подписки');
    }
    setCreating(false);
  }

  async function handleDelete(id: number) {
    setDeletingId(id);
    try {
      await deleteSubscription(id);
      setSubs(prev => prev.filter(s => s.id !== id));
      try { WebApp.HapticFeedback.impactOccurred('medium'); } catch {}
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка удаления');
    }
    setDeletingId(null);
  }

  const hasFilters = !!(currentFilters.query || currentFilters.area || currentFilters.schedule || currentFilters.min_salary);

  return (
    <div>
      {error && (
        <div className="error-box" onClick={() => setError('')} style={{ cursor: 'pointer' }}>
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {/* Current filter preview */}
      <div className="card" style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-3)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Текущие фильтры
        </div>
        {hasFilters ? (
          <div className="card-pills">
            {currentFilters.query && <span className="pill">{currentFilters.query}</span>}
            {currentFilters.area && <span className="pill">📍 {currentFilters.area}</span>}
            {currentFilters.schedule && <span className="pill">{currentFilters.schedule}</span>}
            {currentFilters.min_salary && (
              <span className="pill salary">
                от {currentFilters.min_salary.toLocaleString('ru')} ₽
              </span>
            )}
          </div>
        ) : (
          <div style={{ fontSize: 13, color: 'var(--text-3)' }}>
            Настройте фильтры на вкладке «Поиск»
          </div>
        )}
        <button
          className="btn btn-primary mt-3"
          onClick={handleCreate}
          disabled={creating || !hasFilters}
        >
          {creating ? (
            <><span className="spinner" /> Создаю подписку…</>
          ) : (
            <> Подписаться на эти фильтры</>
          )}
        </button>
      </div>

      {/* Subscriptions list */}
      {loading ? (
        <div className="loading-center">
          <div className="spinner spinner-accent" style={{ width: 28, height: 28 }} />
        </div>
      ) : subs.length === 0 ? (
        <div className="empty-state">
          <span className="empty-icon">🔔</span>
          <div className="empty-title">Подписок пока нет</div>
          <div className="empty-sub">
            Бот пришлёт сообщение, как только<br/>появятся новые вакансии по вашим фильтрам
          </div>
        </div>
      ) : (
        <>
          <div className="count-badge">
            <strong>{subs.length}</strong> активных подписок
          </div>
          {subs.map((s, i) => (
            <div
              className="sub-card"
              key={s.id}
              style={{ animationDelay: `${i * 0.05}s` }}
            >
              <div className="sub-dot" />
              <div className="sub-info">
                <div className="sub-title">{s.query || 'Все вакансии'}</div>
                <div className="sub-meta">{formatFilters(s)}</div>
              </div>
              <button
                className="btn btn-danger btn-sm"
                onClick={() => handleDelete(s.id!)}
                disabled={deletingId === s.id}
                aria-label="Удалить подписку"
              >
                {deletingId === s.id ? <span className="spinner" style={{ width: 14, height: 14 }} /> : '✕'}
              </button>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
