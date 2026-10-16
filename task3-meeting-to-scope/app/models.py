from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Requirement(BaseModel):
    id: str
    transcript_id: str
    project_id: str
    description: str
    source_quote: str
    status: str = "confirmed"  # confirmed | unclear | disputed
    priority: str = "medium"   # high | medium | low
    stated_or_inferred: str = "stated"  # stated | inferred
    feasibility: str = "needs_clarification"
    # existing_config | existing_feature_with_limitation | potential_custom | needs_clarification
    feasibility_detail: str = ""
    existing_solution: Optional[str] = None
    statement_type: str = "requirement_change"
    # requirement_change | decision | timeline_change | confirmation_or_chatter
    extraction_mode: str = "llm"  # llm | offline_heuristic
    acceptance_criteria: Optional[str] = None
    dependencies: list[str] = []
    estimate_status: str = "pending"
    version: int = 1


class EstimateTask(BaseModel):
    name: str
    requirement_id: Optional[str] = None
    low_hours: float
    likely_hours: float
    high_hours: float
    reasoning: str
    assumptions: str = ""
    dependencies: list[str] = []


class ProjectEstimate(BaseModel):
    id: str
    scope_version_id: str
    project_id: str
    tasks: list[EstimateTask] = []
    total_low_hours: float = 0.0
    total_likely_hours: float = 0.0
    total_high_hours: float = 0.0
    hourly_rate: float = 150.0
    currency: str = "USD"
    tax_rate: float = 0.0
    estimated_cost_low: float = 0.0
    estimated_cost_likely: float = 0.0
    estimated_cost_high: float = 0.0
    version: int = 1


class ScopeDocument(BaseModel):
    id: str
    project_id: str
    version: int = 1
    title: str
    objective: str
    current_problem: str
    agreed_requirements: list[Requirement] = []
    proposed_solution: str
    deliverables: list[str] = []
    exclusions: list[str] = []
    assumptions_and_dependencies: list[str] = []
    acceptance_criteria: list[str] = []
    client_responsibilities: list[str] = []
    open_questions_and_risks: list[str] = []
    target_delivery_date: str = "TBD"
    status: str = "draft"  # draft | approved | superseded | degraded_offline
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    extraction_mode: str = "llm"  # llm | offline_heuristic


class ProposalDocument(BaseModel):
    id: str
    project_id: str
    scope_version_id: str
    estimate_id: Optional[str] = None
    title: str
    executive_summary: str
    problem_and_solution: str
    scope_summary: str
    timeline: str
    pricing_breakdown: str
    client_duties: list[str] = []
    exclusions: list[str] = []
    risks_and_mitigations: list[str] = []
    next_steps: list[str] = []
    status: str = "draft"  # draft | approved | sent
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None


class ScopeDiffReport(BaseModel):
    id: str
    project_id: str
    baseline_scope_id: str
    new_transcript_id: str
    added_requirements: list[str] = []
    modified_requirements: list[str] = []
    removed_requirements: list[str] = []
    unchanged_requirements: list[str] = []
    not_a_requirement_items: list[str] = []
    out_of_scope_items: list[str] = []
    conflicts: list[str] = []
    timeline_delta: str = ""
    hours_delta: float = 0.0
    cost_delta: float = 0.0
    summary: str
    extraction_mode: str = "llm"  # llm | offline_heuristic
