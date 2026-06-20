from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class Experience(str, Enum):
    NO_EXPERIENCE = "noExperience"
    BETWEEN_1_AND_3 = "between1And3"
    BETWEEN_3_AND_6 = "between3And6"
    MORE_THAN_6 = "moreThan6"


class Schedule(str, Enum):
    FULL_DAY = "fullDay"
    SHIFT = "shift"
    FLEXIBLE = "flexible"
    REMOTE = "remote"
    ROTATION = "rotation"


class SearchParams(BaseModel):
    query: str = ""
    area: Optional[str] = None
    salary_from: Optional[int] = None
    salary_to: Optional[int] = None
    experience: Optional[Experience] = None
    schedule: Optional[Schedule] = None
    professional_role: Optional[str] = None
    page: int = 0
    per_page: int = 20


class Vacancy(BaseModel):
    id: str
    title: str
    company: str
    city: str = ""
    salary: str = ""
    salary_from: Optional[int] = None
    salary_to: Optional[int] = None
    schedule: str = ""
    experience: str = ""
    skills: list[str] = []
    url: str = ""
    description: str = ""
    published_at: str = ""
    is_mock: bool = False


class VacancyFromHH(BaseModel):
    id: str
    name: str
    employer: dict = {}
    area: dict = {}
    salary: Optional[dict] = None
    schedule: dict = {}
    experience: dict = {}
    key_skills: list[dict] = []
    snippet: Optional[dict] = None
    alternate_url: str = ""
    published_at: str = ""


class AnalysisResult(BaseModel):
    vacancy_id: str
    rank: int = Field(ge=1, le=10)
    fit_score: int = Field(ge=1, le=10, description="Насколько подходит (1-10)")
    why_fits: str = ""
    concerns: str = ""
    summary: str = ""
    recommendation: str = ""


class CriteriaInput(BaseModel):
    direction: str = ""
    city: str = ""
    remote_only: bool = False
    min_salary: Optional[int] = None
    experience_level: str = ""
    key_skills: list[str] = []
    date_from: Optional[str] = None


class Subscription(BaseModel):
    id: Optional[int] = None
    chat_id: int
    query: str = ""
    area: Optional[str] = None
    schedule: Optional[str] = None
    min_salary: Optional[int] = None
    is_active: bool = True


class Favorite(BaseModel):
    id: Optional[int] = None
    chat_id: int = 0
    vacancy_id: str
    title: str
    company: str
    url: str = ""
