from dataclasses import dataclass, field


@dataclass
class SpecialistOutput:

    agent: str

    status: str

    analysis: str

    # Deterministic one-paragraph digest built by each specialist's
    # parse_response(). Consumed by the Explanation Engine (13Q).
    summary: str = ""

    risks: list = field(default_factory=list)

    opportunities: list = field(default_factory=list)

    confidence: float = 0.0

    metadata: dict = field(default_factory=dict)