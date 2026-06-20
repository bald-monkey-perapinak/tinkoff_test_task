import WebApp from '@twa-dev/sdk';
import { AnalysisResult, Vacancy } from '../types';
import { AnalysisPanel } from './AnalysisPanel';

interface Props {
  results: AnalysisResult[];
  report: string;
  analyzing: boolean;
  onAnalyze: () => void;
  onOpenUrl: (url: string) => void;
  onExport: (format: 'json' | 'csv') => void;
}

export function AnalysisTab({ results, report, analyzing, onAnalyze, onOpenUrl, onExport }: Props) {
  const handleDownloadReport = () => {
    const blob = new Blob([report], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'vacancy-report.md';
    a.click();
    URL.revokeObjectURL(url);
    WebApp.HapticFeedback.impactOccurred('light');
  };

  return (
    <>
      <button className="btn btn-primary" onClick={onAnalyze} disabled={analyzing} style={{ width: '100%', marginBottom: 12 }}>
        {analyzing ? 'AI анализирует...' : 'AI-проанализировать вакансии'}
      </button>
      <AnalysisPanel results={results} onOpenUrl={onOpenUrl} />
      {report && (
        <>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <button className="btn btn-outline" onClick={handleDownloadReport} style={{ flex: 1 }}>
              Скачать .md
            </button>
            <button className="btn btn-outline" onClick={() => onExport('csv')} style={{ flex: 1 }}>
              Скачать .csv
            </button>
            <button className="btn btn-outline" onClick={() => onExport('json')} style={{ flex: 1 }}>
              Скачать .json
            </button>
          </div>
          <div className="report-view">{report}</div>
        </>
      )}
    </>
  );
}
