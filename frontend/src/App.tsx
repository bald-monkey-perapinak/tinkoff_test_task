import { useEffect, useCallback } from 'react';
import WebApp from '@twa-dev/sdk';
import { useVacancyAgent } from './hooks/useVacancyAgent';
import { SearchTab } from './components/SearchTab';
import { AnalysisTab } from './components/AnalysisTab';
import { UploadTab } from './components/UploadTab';
import { SubscriptionsTab } from './components/SubscriptionsTab';

export default function App() {
  const {
    tab, setTab,
    query, setQuery,
    areaName,
    salaryFrom, setSalaryFrom,
    schedule, setSchedule,
    experience, setExperience,
    remoteOnly, setRemoteOnly,
    dateFrom, setDateFrom,
    vacancies, total, results, report,
    favorites,
    searching, analyzing, uploading,
    areaSuggestions, loadingMore, hasMore,
    handleSearch, handleAreaSearch, handleSelectArea,
    handleAnalyze, handleUpload, toggleFavorite,
    handleLoadMore, handleExport, openVacancyUrl,
  } = useVacancyAgent();

  const handleBackToSearch = useCallback(() => {
    setTab('search');
  }, [setTab]);

  const handleAnalyzeClick = useCallback(() => {
    handleAnalyze();
  }, [handleAnalyze]);

  const handleUploadClick = useCallback(() => {
    const input = document.querySelector<HTMLInputElement>('input[type="file"]');
    input?.click();
  }, []);

  useEffect(() => {
    WebApp.MainButton.hide();
    WebApp.BackButton.hide();

    if (tab === 'search' && vacancies.length > 0) {
      WebApp.MainButton.setText('AI-проанализировать');
      WebApp.MainButton.show();
      WebApp.MainButton.onClick(handleAnalyzeClick);
    }

    if (tab === 'analysis' && results.length > 0) {
      WebApp.BackButton.show();
      WebApp.BackButton.onClick(handleBackToSearch);
    }

    if (tab === 'upload') {
      WebApp.MainButton.setText('Загрузить файл');
      WebApp.MainButton.show();
      WebApp.MainButton.onClick(handleUploadClick);
    }

    return () => {
      WebApp.MainButton.offClick(handleAnalyzeClick);
      WebApp.MainButton.offClick(handleUploadClick);
      WebApp.BackButton.offClick(handleBackToSearch);
    };
  }, [tab, vacancies, results, handleAnalyzeClick, handleUploadClick, handleBackToSearch]);

  const currentFilters = { query, area: areaName, schedule, min_salary: salaryFrom ? parseInt(salaryFrom) : null };

  return (
    <div className="app" style={{ paddingTop: 'var(--tg-safe-area-inset-top)' }}>
      <div className="tabs" role="tablist" aria-label="Main navigation">
        <button className={`tab ${tab === 'search' ? 'active' : ''}`} role="tab" aria-selected={tab === 'search'} onClick={() => setTab('search')}>
          Поиск
        </button>
        <button className={`tab ${tab === 'analysis' ? 'active' : ''}`} role="tab" aria-selected={tab === 'analysis'} onClick={() => setTab('analysis')}>
          AI-анализ
        </button>
        <button className={`tab ${tab === 'upload' ? 'active' : ''}`} role="tab" aria-selected={tab === 'upload'} onClick={() => setTab('upload')}>
          Загрузка
        </button>
        <button className={`tab ${tab === 'subs' ? 'active' : ''}`} role="tab" aria-selected={tab === 'subs'} onClick={() => setTab('subs')}>
          Уведомления
        </button>
      </div>

      {tab === 'search' && (
        <SearchTab
          query={query}
          setQuery={setQuery}
          areaName={areaName}
          salaryFrom={salaryFrom}
          setSalaryFrom={setSalaryFrom}
          schedule={schedule}
          setSchedule={setSchedule}
          experience={experience}
          setExperience={setExperience}
          remoteOnly={remoteOnly}
          setRemoteOnly={setRemoteOnly}
          dateFrom={dateFrom}
          setDateFrom={setDateFrom}
          vacancies={vacancies}
          total={total}
          favorites={favorites}
          searching={searching}
          areaSuggestions={areaSuggestions}
          loadingMore={loadingMore}
          hasMore={hasMore}
          onSearch={handleSearch}
          onAreaSearch={handleAreaSearch}
          onSelectArea={handleSelectArea}
          onToggleFavorite={toggleFavorite}
          onLoadMore={handleLoadMore}
          onOpenUrl={openVacancyUrl}
        />
      )}

      {tab === 'analysis' && (
        <AnalysisTab
          results={results}
          report={report}
          analyzing={analyzing}
          onAnalyze={handleAnalyze}
          onOpenUrl={openVacancyUrl}
          onExport={handleExport}
        />
      )}

      {tab === 'upload' && (
        <UploadTab
          vacancies={vacancies}
          favorites={favorites}
          uploading={uploading}
          onFileSelect={handleUpload}
          onToggleFavorite={toggleFavorite}
          onOpenUrl={openVacancyUrl}
        />
      )}

      {tab === 'subs' && (
        <SubscriptionsTab currentFilters={currentFilters} />
      )}
    </div>
  );
}
