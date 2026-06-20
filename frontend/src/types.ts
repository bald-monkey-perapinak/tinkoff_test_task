export interface Vacancy {
  id: string;
  title: string;
  company: string;
  city: string;
  salary: string;
  salary_from: number | null;
  salary_to: number | null;
  schedule: string;
  experience: string;
  skills: string[];
  url: string;
  description: string;
  published_at: string;
  is_mock: boolean;
}

export interface AnalysisResult {
  vacancy_id: string;
  rank: number;
  fit_score: number;
  why_fits: string;
  concerns: string;
  summary: string;
  recommendation: string;
  vacancy?: Vacancy;
}

export interface Criteria {
  direction: string;
  city: string;
  remote_only: boolean;
  min_salary: number | null;
  experience_level: string;
  key_skills: string[];
  date_from: string | null;
}

export interface Favorite {
  id?: number;
  vacancy_id: string;
  title: string;
  company: string;
  url: string;
}

export interface Subscription {
  id?: number;
  chat_id: number;
  query: string;
  area: string | null;
  schedule: string | null;
  min_salary: number | null;
  is_active: boolean;
}

export interface SearchResult {
  vacancies: Vacancy[];
  total: number;
}

export interface Area {
  id: string;
  name: string;
}
