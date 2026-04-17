import asyncio
import os
import sys
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from persona_bot_fast import FastPersonaBot
    from response_cache import CachedPersonaBot
    HAS_FAST_BOT = True
except ImportError:
    HAS_FAST_BOT = False
    print("Warning: persona_bot_fast not available")

try:
    from persona_bot_enhanced import EnhancedPersonaBot
    HAS_ENHANCED_BOT = True
except ImportError:
    HAS_ENHANCED_BOT = False
    print("Warning: persona_bot_enhanced not available")

try:
    from persona_bot_safe import PersonaBot
    HAS_PERSONA_BOT = True
except ImportError:
    HAS_PERSONA_BOT = False
    print("Warning: persona_bot_safe not available")

try:
    from voice_generator import VoiceGenerator
    HAS_VOICE = True
except ImportError:
    HAS_VOICE = False
    print("Warning: voice_generator not available")

try:
    from project_mapper import suggest_projects
    HAS_PROJECT_MAPPER = True
except ImportError:
    HAS_PROJECT_MAPPER = False
    print("Warning: project_mapper not available")

app = FastAPI(title="Lecture Bot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://perfectpixels.com",
        "https://www.perfectpixels.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Config from env (aligned with ppmg)
KB_ID = os.environ.get("BEDROCK_KNOWLEDGE_BASE_ID", "HHYCUJH32J")
MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"
)
CHAT_TIMEOUT_SECONDS = float(os.environ.get("CHAT_TIMEOUT_SECONDS", "25"))
RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "30"))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))
CHAT_MAX_RESULTS = int(os.environ.get("CHAT_MAX_RESULTS", "6"))

bot = None
voice_gen = None

if HAS_FAST_BOT:
    try:
        persona_name = os.environ.get("PERSONA_NAME", "Jason Levine")
        use_haiku = os.environ.get("USE_HAIKU", "false").lower() == "true"
        fast_bot = FastPersonaBot(
            KB_ID, MODEL_ID, persona_name=persona_name, use_haiku=use_haiku
        )
        bot = CachedPersonaBot(fast_bot, cache_ttl_hours=24)
        print("✓ Fast PersonaBot with caching initialized")
    except Exception as e:
        print(f"Error initializing Fast PersonaBot: {e}")
elif HAS_ENHANCED_BOT:
    try:
        bot = EnhancedPersonaBot(KB_ID, MODEL_ID)
        print("✓ EnhancedPersonaBot initialized")
    except Exception as e:
        print(f"Error initializing EnhancedPersonaBot: {e}")
elif HAS_PERSONA_BOT:
    try:
        bot = PersonaBot(KB_ID, MODEL_ID)
        print("✓ PersonaBot initialized")
    except Exception as e:
        print(f"Error initializing PersonaBot: {e}")

if HAS_VOICE:
    try:
        voice_gen = VoiceGenerator()
        print("✓ VoiceGenerator initialized")
    except Exception as e:
        print(f"Error initializing VoiceGenerator: {e}")


_rate_limit_buckets: Dict[str, Deque[float]] = defaultdict(deque)
_rate_limit_lock = Lock()


def _client_id_from_request(request: Request) -> str:
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _check_rate_limit(client_id: str) -> bool:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS

    with _rate_limit_lock:
        bucket = _rate_limit_buckets[client_id]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_REQUESTS:
            return False
        bucket.append(now)
        return True


class ChatRequest(BaseModel):
    message: str
    voice_enabled: bool = True
    project_slug: Optional[str] = None
    response_language: str = Field(
        default="en",
        description='Reply language: "en" (English) or "zh" (简体中文).',
    )


class ChatResponse(BaseModel):
    answer: str
    audio_base64: Optional[str] = None
    sources: List[str] = []
    relevant_concepts: List[str] = []
    suggested_projects: List[Dict[str, str]] = []


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request):
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    client_id = _client_id_from_request(http_request)
    if not _check_rate_limit(client_id):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait a moment before trying again.",
        )

    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if len(message) > 1000:
        raise HTTPException(
            status_code=400, detail="Message too long (max 1000 characters)"
        )

    try:
        lang = request.response_language if request.response_language in ("en", "zh") else "en"

        def _run_query():
            try:
                return bot.query(
                    message,
                    CHAT_MAX_RESULTS,
                    True,
                    response_language=lang,
                )
            except TypeError:
                return bot.query(message, CHAT_MAX_RESULTS, True)

        result = await asyncio.wait_for(
            run_in_threadpool(_run_query),
            timeout=CHAT_TIMEOUT_SECONDS,
        )

        suggested_projects = []
        if HAS_PROJECT_MAPPER:
            try:
                raw_suggestions = suggest_projects(
                    message, max_suggestions=2, exclude_slug=request.project_slug
                )
                suggested_projects = [
                    {
                        "slug": proj["slug"],
                        "title": proj["title"],
                        "description": proj["description"],
                    }
                    for proj in raw_suggestions
                ]
            except Exception as e:
                print(f"Project suggestion failed: {e}")

        audio_base64 = None
        if request.voice_enabled and voice_gen and lang == "en":
            try:
                audio_base64 = voice_gen.generate_audio_base64(
                    result["answer"], voice="chris"
                )
            except Exception as e:
                print(f"Voice generation failed: {e}")

        return ChatResponse(
            answer=result["answer"],
            audio_base64=audio_base64,
            sources=result.get("sources", []),
            relevant_concepts=result.get("relevant_concepts", []),
            suggested_projects=suggested_projects,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Chat request timed out after {CHAT_TIMEOUT_SECONDS:.0f}s",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal chat processing error")


@app.get("/api/health")
async def health(deep: bool = False):
    if not bot:
        return {
            "status": "degraded",
            "bot_initialized": False,
            "bedrock_reachable": False,
        }

    if not deep:
        return {
            "status": "ok",
            "bot_initialized": True,
            "bedrock_reachable": True,
        }

    try:
        healthy = await asyncio.wait_for(
            run_in_threadpool(bot.health_check),
            timeout=8,
        )
        return {
            "status": "ok" if healthy else "degraded",
            "bot_initialized": True,
            "bedrock_reachable": bool(healthy),
        }
    except Exception:
        return {
            "status": "degraded",
            "bot_initialized": True,
            "bedrock_reachable": False,
        }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
