import re
from typing import List, Dict, Any, Tuple
from loguru import logger

class ContextOptimizer:
    """Optimizes LLM context by ranking, selecting, and deduplicating information chunks."""

    def optimize(self, content_items: List[str], query: str, max_tokens: int = 4000, compression_level: str = "moderate", domain_template: str = "general") -> str:
        """
        Ranks paragraphs/sentences from content_items by query relevance,
        selects top matches, and joins them to fit within max_tokens.
        Supports multi-level compression and domain-specific template filtering.
        """
        if not content_items:
            return ""

        query_terms = set(re.findall(r'\b\w{3,}\b', query.lower()))
        
        # 1. Break content into paragraph chunks
        chunks = []
        seen_chunks = set()
        
        for item in content_items:
            # Basic domain template filtering (strip common boilerplate)
            if domain_template == "financial":
                item = re.sub(r'(?i)(forward-looking statements|safe harbor).*', '', item)
            elif domain_template == "news":
                item = re.sub(r'(?i)(subscribe now|read more|advertisement|click here).*', '', item)
                
            # Split by paragraph
            paragraphs = item.split("\n\n")
            for para in paragraphs:
                para = para.strip()
                if not para or len(para) < 40: # Skip very short snippets/headers
                    continue
                
                # Check duplicate
                para_hash = hash(para)
                if para_hash in seen_chunks:
                    continue
                seen_chunks.add(para_hash)
                chunks.append(para)

        # 2. Score chunks by term overlap
        scored_chunks = []
        for chunk in chunks:
            chunk_lower = chunk.lower()
            overlap_score = 0.0
            
            # Simple keyword matching
            for term in query_terms:
                if term in chunk_lower:
                    overlap_score += 1.0
                    
            # Bonus for exact query substring match
            if query.lower() in chunk_lower:
                overlap_score += 5.0
                
            # Compression logic: if aggressive, heavily penalize low scoring chunks
            if compression_level == "aggressive" and overlap_score < 2.0:
                continue
                
            scored_chunks.append((chunk, overlap_score))

        # Sort descending by score
        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        # 3. Select top chunks fitting the budget (1 token ≈ 4 characters)
        max_chars = max_tokens * 4
        
        # Adjust char limit based on compression level
        if compression_level == "aggressive":
            max_chars = int(max_chars * 0.5)
            
        selected_chunks = []
        current_chars = 0
        
        for chunk, score in scored_chunks:
            # If the best score is 0 and we already have some chunks, stop
            if score == 0.0 and len(selected_chunks) >= 5:
                break
                
            chunk_len = len(chunk)
            if current_chars + chunk_len > max_chars:
                # If chunk is too long, we might truncate or skip
                if len(selected_chunks) == 0:
                    selected_chunks.append(chunk[:max_chars])
                break
            
            selected_chunks.append(chunk)
            current_chars += chunk_len

        logger.info(f"Context optimized ({compression_level}, {domain_template}): selected {len(selected_chunks)} chunks out of {len(chunks)} total.")
        return "\n\n".join(selected_chunks)
