"""Request and response models. Pydantic validates every input before any code runs."""

from typing import List, Optional

from pydantic import BaseModel, Field


class Program(BaseModel):
    program_id: int
    university: str
    program_name: str
    tier: Optional[str] = None
    course_count: int


class ProgramPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[Program]


class Gap(BaseModel):
    skill: str
    market_demand_rate: float = Field(description="Share of job postings that mention the skill (0 to 1)")
    program_coverage_rate: float = Field(description="Share of the program's courses that mention the skill (0 to 1)")
    gap_value: float
    q_value: Optional[float] = Field(None, description="Benjamini-Hochberg corrected p-value; every returned gap has q < 0.05")
    test_method: Optional[str] = None
    priority_tier: Optional[str] = None
    priority_score: Optional[float] = None
    trend_label: Optional[str] = None
    rationale: Optional[str] = None


class GapPage(BaseModel):
    program: Program
    scope: str
    total: int
    limit: int
    offset: int
    items: List[Gap]


class MatchRequest(BaseModel):
    job_text: str = Field(min_length=20, max_length=20_000, description="The full job posting text")
    my_skills: str = Field("", max_length=20_000, description="Your skills or resume text (optional)")


class SkillRef(BaseModel):
    skill: str
    market_demand_rate: float


class MatchResponse(BaseModel):
    skills_in_posting: int
    have: List[SkillRef]
    missing: List[SkillRef] = Field(description="Ordered by how often employers ask for the skill, most common first")
    match_fraction: Optional[float] = Field(None, description="have / skills_in_posting, or null if no skills were supplied")


class Health(BaseModel):
    status: str
    database: str
    version: str
