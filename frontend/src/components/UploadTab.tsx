import { Vacancy } from '../types';
import { FileUpload } from './FileUpload';
import { VacancyList } from './VacancyList';

interface Props {
  vacancies: Vacancy[];
  favorites: Set<string>;
  uploading: boolean;
  onFileSelect: (file: File) => void;
  onToggleFavorite: (v: Vacancy) => void;
  onOpenUrl: (url: string) => void;
}

export function UploadTab({ vacancies, favorites, uploading, onFileSelect, onToggleFavorite, onOpenUrl }: Props) {
  return (
    <>
      <FileUpload onFileSelect={onFileSelect} isLoading={uploading} />
      {vacancies.length > 0 && (
        <>
          <div className="total-badge">Загружено: {vacancies.length} вакансий</div>
          <VacancyList
            vacancies={vacancies}
            favorites={favorites}
            onToggleFavorite={onToggleFavorite}
            onOpenUrl={onOpenUrl}
          />
        </>
      )}
    </>
  );
}
