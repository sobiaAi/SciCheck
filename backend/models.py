from typing import Literal
from pydantic import BaseModel, Field


Domain = Literal["genomics", "neuroscience", "cardiac"]
Severity = Literal["Critical", "High", "Medium"]


class AnalyzeRequest(BaseModel):
    code: str = Field(..., min_length=1)
    domain: Domain


class FileInput(BaseModel):
    name: str = Field(..., min_length=1)
    content: str = Field(...)


class AnalyzeFilesRequest(BaseModel):
    files: list[FileInput] = Field(..., min_length=1)
    domain: Domain


class Finding(BaseModel):
    pattern_id: str
    pattern_name: str
    severity: Severity
    found: bool
    finding: str
    line_reference: str
    doc_link: str


class AnalyzeResponse(BaseModel):
    domain: Domain
    patterns_checked: int
    analysis_time_seconds: float
    findings: list[Finding]
    clean: bool
