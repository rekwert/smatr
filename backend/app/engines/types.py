from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class EngineEvent:
    type: str
    direction: Optional[str] = None
    strength: float = 0.0
    price: Optional[float] = None
    top: Optional[float] = None
    bottom: Optional[float] = None
    index: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data
