from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Pattern:
    id: str
    name: str
    severity: Literal["Critical", "High", "Medium"]
    doc_link: str
    detection_prompt: str
    # imports that must be present for this pattern to be relevant (empty = always run)
    trigger_imports: tuple[str, ...] = field(default_factory=tuple)
    # functions whose output variables are traced via RLT for cross-file context
    seed_functions: tuple[str, ...] = field(default_factory=tuple)
