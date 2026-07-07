from typing import Dict, Any
from deployment.runtime.models.research_strategy import ResearchStrategy

class CostEstimator:
    """
    Estimates latency and token costs for a given research strategy before execution.
    """
    
    def estimate(self, strategy: ResearchStrategy) -> Dict[str, Any]:
        """
        Calculates estimated cost metrics for UI feedback.
        """
        budget = strategy.execution_budget
        
        # Base latency logic
        # 1 search ≈ 1s, 1 fetch ≈ 1.5s, 1 LLM call ≈ 3s
        base_search_time = 1.0 * (budget.max_searches or 0)
        base_fetch_time = 1.5 * (budget.max_fetches or 0)
        base_llm_time = 3.0 * (budget.max_llm_calls or 0)
        
        # Parallel factor (assume searches/fetches can be parallelized slightly)
        parallel_search_time = max(1.0, base_search_time * 0.5)
        parallel_fetch_time = max(1.5, base_fetch_time * 0.3)
        
        estimated_latency = parallel_search_time + parallel_fetch_time + base_llm_time
        
        # Refine by strategy type
        if strategy.strategy_name == "FAST":
            estimated_latency = 1.5
        elif strategy.strategy_name == "LOOKUP":
            estimated_latency = 3.0
            
        # Estimate token usage
        # Fetching pages ≈ 3000 tokens each
        # Output generation ≈ 1000 tokens
        input_tokens = (budget.max_fetches or 0) * 3000
        output_tokens = (budget.max_llm_calls or 0) * 1000
        
        if strategy.strategy_name == "FAST":
            input_tokens = 500
        elif strategy.strategy_name == "LOOKUP":
            input_tokens = 1000
            output_tokens = 0 # Handled by direct snippet concatenation
            
        cost_category = "Low"
        if input_tokens > 20000 or output_tokens > 5000:
            cost_category = "High"
        elif input_tokens > 8000 or output_tokens > 2000:
            cost_category = "Medium"
            
        return {
            "estimated_latency_seconds": round(estimated_latency, 1),
            "estimated_input_tokens": input_tokens,
            "estimated_output_tokens": output_tokens,
            "cost_category": cost_category
        }
