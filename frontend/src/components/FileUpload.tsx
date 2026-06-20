import { useRef, useState } from 'react';

interface Props {
  onFileSelect: (file: File) => void;
  isLoading: boolean;
}

export function FileUpload({ onFileSelect, isLoading }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) onFileSelect(file);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFileSelect(file);
    e.target.value = '';
  };

  return (
    <div>
      <div
        className={`upload-zone${dragging ? ' drag-over' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !isLoading && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={e => e.key === 'Enter' && inputRef.current?.click()}
        aria-label="Загрузить файл с вакансиями"
      >
        {isLoading ? (
          <>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 14 }}>
              <div className="spinner spinner-accent" style={{ width: 36, height: 36 }} />
            </div>
            <div className="upload-title">Загружаю файл…</div>
            <div className="upload-sub">Это займёт несколько секунд</div>
          </>
        ) : (
          <>
            <span className="upload-icon">{dragging ? '📂' : '📁'}</span>
            <div className="upload-title">
              {dragging ? 'Отпустите файл' : 'Перетащите файл сюда'}
            </div>
            <div className="upload-sub">или нажмите для выбора</div>
            <div className="upload-hint">
              <span className="pill" style={{ fontSize: 11 }}>JSON</span>
              <span className="pill" style={{ fontSize: 11 }}>CSV</span>
              <span className="pill" style={{ fontSize: 11 }}>до 5 МБ</span>
            </div>
          </>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".json,.csv"
        onChange={handleChange}
        style={{ display: 'none' }}
        aria-hidden="true"
      />

      {/* Format hint */}
      <div
        className="card"
        style={{ marginTop: 14, background: 'var(--s1)', borderColor: 'var(--border)' }}
      >
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)', marginBottom: 8 }}>
          Формат файла
        </div>
        <pre
          style={{
            fontSize: 11,
            color: 'var(--text-3)',
            overflowX: 'auto',
            lineHeight: 1.6,
            fontFamily: "'SF Mono', 'Fira Code', monospace",
          }}
        >{`[
  {
    "title": "Junior Python Dev",
    "company": "Тинькофф",
    "city": "Москва",
    "salary": "от 80 000 ₽",
    "salary_from": 80000,
    "skills": ["Python", "SQL"],
    "url": "https://hh.ru/vacancy/123"
  }
]`}</pre>
      </div>
    </div>
  );
}
