from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

SpecialistName = str  # "research" | "data_analysis" | "writing" | "code_execution" (milestone 2+)


class Subtask(BaseModel):
    id: str = Field(description="Short unique id, e.g. 'st-1'")
    description: str
    assigned_specialist: SpecialistName
    depends_on: list[str] = Field(default_factory=list, description="ids of subtasks that must complete first")
    required_inputs: str = Field(description="What inputs/context this subtask needs")
    expected_output_format: str = Field(description="What form the output should take, e.g. 'bulleted list of facts'")
    estimated_complexity: int = Field(ge=1, le=5, description="1=trivial, 5=very complex")


class ExecutionPlan(BaseModel):
    subtasks: list[Subtask]
    confidence: float = Field(ge=0.0, le=1.0, description="Supervisor's confidence this plan will succeed")
    reasoning: str = Field(description="Brief rationale for the decomposition")


class SubtaskResult(BaseModel):
    subtask_id: str
    output: str
    tool_calls: list[str] = Field(default_factory=list)
    success: bool = True
    error: str | None = None


class ReviewVerdict(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewResult(BaseModel):
    subtask_id: str
    verdict: ReviewVerdict
    quality_score: float = Field(ge=0.0, le=1.0)
    feedback: str = Field(description="Actionable feedback if rejected; brief note if approved")
