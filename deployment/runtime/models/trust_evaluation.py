from pydantic import BaseModel

class TrustEvaluation(BaseModel):
    """Evaluation score and explanation of a source's trustworthiness."""
    authority: float = 0.0          # 0.0 to 100.0
    freshness: float = 0.0          # 0.0 to 100.0
    bias: float = 0.0               # 0.0 to 100.0 (high score = low bias/more neutral)
    quality: float = 0.0            # 0.0 to 100.0
    citations: float = 0.0          # 0.0 to 100.0
    overall_score: float = 0.0      # 0.0 to 100.0
    reason: str = ""
