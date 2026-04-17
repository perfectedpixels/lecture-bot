"""
Response caching layer for faster repeated queries.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict


class ResponseCache:
    """
    Cache responses to avoid repeated LLM calls for similar queries.
    """
    
    def __init__(self, cache_dir: str = ".cache", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        
        # In-memory cache for current session
        self.memory_cache = {}
    
    def _get_cache_key(self, query: str, kb_id: str) -> str:
        """Generate cache key from query and KB ID"""
        content = f"{kb_id}:{query.lower().strip()}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get file path for cache key"""
        return self.cache_dir / f"{cache_key}.json"
    
    def get(self, query: str, kb_id: str) -> Optional[Dict]:
        """Get cached response if available and not expired"""
        
        cache_key = self._get_cache_key(query, kb_id)
        
        # Check memory cache first
        if cache_key in self.memory_cache:
            return self.memory_cache[cache_key]
        
        # Check disk cache
        cache_path = self._get_cache_path(cache_key)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r') as f:
                cached = json.load(f)
            
            # Check if expired
            cached_time = datetime.fromisoformat(cached['timestamp'])
            if datetime.now() - cached_time > self.ttl:
                cache_path.unlink()  # Delete expired cache
                return None
            
            # Add to memory cache
            self.memory_cache[cache_key] = cached['response']
            return cached['response']
            
        except Exception as e:
            print(f"Cache read error: {e}")
            return None
    
    def set(self, query: str, kb_id: str, response: Dict):
        """Cache a response"""
        
        cache_key = self._get_cache_key(query, kb_id)
        cache_path = self._get_cache_path(cache_key)
        
        cached_data = {
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'response': response
        }
        
        try:
            with open(cache_path, 'w') as f:
                json.dump(cached_data, f)
            
            # Add to memory cache
            self.memory_cache[cache_key] = response
            
        except Exception as e:
            print(f"Cache write error: {e}")
    
    def clear_expired(self):
        """Clear expired cache entries"""
        
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r') as f:
                    cached = json.load(f)
                
                cached_time = datetime.fromisoformat(cached['timestamp'])
                if datetime.now() - cached_time > self.ttl:
                    cache_file.unlink()
                    
            except Exception:
                continue
    
    def clear_all(self):
        """Clear all cache"""
        
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
        
        self.memory_cache.clear()
        print("Cache cleared")


class CachedPersonaBot:
    """
    Wrapper that adds caching to any PersonaBot.
    Uses cache_namespace (kb_id:model:version) for invalidation on model changes.
    """
    
    def __init__(self, bot, cache_ttl_hours: int = 24):
        self.bot = bot
        self.cache = ResponseCache(ttl_hours=cache_ttl_hours)
        cache_model = getattr(bot, "model_id", "unknown-model")
        cache_version = getattr(bot, "cache_version", "v1")
        self.cache_namespace = f"{bot.knowledge_base_id}:{cache_model}:{cache_version}"
    
    def query(self, question: str, max_results: int = 6, use_persona: bool = True, response_language: str = "en", **kwargs) -> dict:
        """Query with caching. response_language: en | zh (separate cache per language)."""

        cache_ns = f"{self.cache_namespace}:{response_language}"

        cached = self.cache.get(question, cache_ns)
        if cached:
            print("✓ Cache hit")
            return cached

        try:
            result = self.bot.query(
                question,
                max_results,
                use_persona,
                response_language=response_language,
                **kwargs,
            )
        except TypeError:
            result = self.bot.query(
                question, max_results, use_persona, **kwargs
            )
        
        self.cache.set(question, cache_ns, result)
        
        return result
    
    def generate_report(self, topic: str) -> str:
        """Generate report (not cached)"""
        return self.bot.generate_report(topic)
    
    def analyze_assignment(self, assignment_text: str) -> dict:
        """Analyze assignment (not cached)"""
        return self.bot.analyze_assignment(assignment_text)
    
    def explain_concept(self, concept: str) -> dict:
        """Explain concept with caching"""
        
        cached = self.cache.get(f"explain:{concept}", self.cache_namespace)
        if cached:
            print("✓ Cache hit")
            return cached
        
        result = self.bot.explain_concept(concept)
        self.cache.set(f"explain:{concept}", self.cache_namespace, result)
        
        return result
    
    def clear_cache(self):
        """Clear cache"""
        self.cache.clear_all()

    def health_check(self) -> bool:
        """Delegate health check to wrapped bot when available."""
        if hasattr(self.bot, "health_check"):
            return bool(self.bot.health_check())
        return True


if __name__ == "__main__":
    # Test caching
    from persona_bot_fast import FastPersonaBot
    
    kb_id = "YOUR_KB_ID"
    
    # Create cached bot
    fast_bot = FastPersonaBot(kb_id)
    cached_bot = CachedPersonaBot(fast_bot, cache_ttl_hours=24)
    
    # First query (slow)
    print("First query...")
    result1 = cached_bot.query("What is UX design?")
    
    # Second query (fast - from cache)
    print("\nSecond query (should be cached)...")
    result2 = cached_bot.query("What is UX design?")
    
    print(f"\nSame result: {result1 == result2}")
