from pydantic import BaseModel

class ResearchStatistics(BaseModel):
    """Execution statistics for a research run."""
    elapsed_time: float = 0.0
    iterations: int = 0
    tool_calls: int = 0
    llm_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    downloaded_sources: int = 0
    cached_sources: int = 0
    assets_created: int = 0
    evidence_documents: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    errors: int = 0
    warnings: int = 0
    
    # Extended metrics
    total_execution_time: float = 0.0
    average_tool_execution_time: float = 0.0
    average_llm_response_time: float = 0.0
    provider_latency: float = 0.0
    total_download_size: int = 0
    cache_saved_downloads: int = 0
    cache_saved_tokens: int = 0
