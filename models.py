"""
Pydantic models for request/response validation.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ImplementationLocation(BaseModel):
    """Location of feature implementation in code."""
    file: str = Field(..., description="Path to the file")
    function: str = Field(..., description="Function or method name")
    lines: str = Field(..., description="Line numbers (e.g., '13-16')")


class FeatureAnalysis(BaseModel):
    """Analysis of a single feature."""
    feature_description: str = Field(..., description="Description of the feature")
    implementation_location: List[ImplementationLocation] = Field(
        ..., description="List of locations where this feature is implemented"
    )


class AnalysisReport(BaseModel):
    """Complete code analysis report."""
    project_structure: str = Field(
        ..., description="Text representation of the project structure"
    )
    feature_analysis: List[FeatureAnalysis] = Field(
        ..., description="List of analyzed features"
    )
    execution_plan_suggestion: str = Field(
        ..., description="Suggestions for running the project"
    )


class RunAndTestRequest(BaseModel):
    """Request model for run-and-test endpoint."""
    analysis_report: Dict[str, Any] = Field(
        ..., description="Analysis report from /api/analyze endpoint"
    )
    base_directory: str = Field(
        ..., description="Base directory of the codebase"
    )
    max_retries: int = Field(
        default=3, description="Maximum retry attempts per feature"
    )
