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

export function SubscriptionsTab({ currentFilters }: Props) {
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadSubs();
  }, []);

  async function loadSubs() {
    setLoading(true);
    setError('');
    try {
      const data = await getSubscriptions();
      setSubs(data.subscriptions);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Неизвестная ошибка';
      setError(`Не удалось загрузить подписки: ${msg}`);
    }
    setLoading(false);
  }

  async function handleCreate() {
    const chatId = getChatId();
    if (!chatId) {
      setError('Не удалось определить ID пользователя Telegram. Откройте приложение в Telegram.');
      return;
    }
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
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Неизвестная ошибка';
      setError(`Ошибка создания подписки: ${msg}`);
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteSubscription(id);
      await loadSubs();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Неизвестная ошибка';
      setError(`Ошибка удаления подписки: ${msg}`);
    }
  }

  if (loading) {
    return <div className="loading"><span className="spinner" /></div>;
  }

  return (
    <div className="section">
      {error && <div role="alert" className="error-banner" style={{ color: 'var(--danger, #e74c3c)', padding: 8, marginBottom: 12, fontSize: 13 }}>{error}</div>}

      <button className="btn btn-primary" onClick={handleCreate} style={{ width: '100%', marginBottom: 12 }}>
        Создать подписку по текущим фильтрам
      </button>

      {subs.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🔔</div>
          <div>Нет активных подписок</div>
        </div>
      ) : (
        subs.map((s) => (
          <div className="sub-card" key={s.id}>
            <div className="sub-info">
              <div className="sub-title">{s.query || 'Все вакансии'}</div>
              <div className="sub-filters">
                {[s.area, s.schedule, s.min_salary ? `от ${s.min_salary} ₽` : null]
                  .filter(Boolean)
                  .join(' · ') || 'Без фильтров'}
              </div>
            </div>
            <button className="btn btn-danger btn-sm" onClick={() => handleDelete(s.id!)}>
              Удалить
            </button>
          </div>
        ))
      )}
    </div>
  );
}
