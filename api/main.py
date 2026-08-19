import asyncio
import json
import os
import sys
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager, AsyncExitStack
from threading import Lock
from typing import Any, Deque, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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

try:
    import explore_topic
    HAS_EXPLORE = True
except ImportError:
    HAS_EXPLORE = False
    print("Warning: explore_topic not available")

try:
    import boards_store
    HAS_BOARDS = True
except ImportError:
    HAS_BOARDS = False
    print("Warning: boards_store not available")

try:
    from feedback_mode import classify_intent, run_feedback_stream
    HAS_FEEDBACK = True
except ImportError:
    HAS_FEEDBACK = False
    print("Warning: feedback_mode not available")

try:
    from canvas_assignments import (
        get_next_due_assignments,
        get_assignment_by_id,
        build_homework_help_prompt,
    )
    HAS_CANVAS = True
except ImportError:
    HAS_CANVAS = False
    print("Warning: canvas_assignments not available")

try:
    from . import mcp_server
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    print("Warning: mcp_server not available (mcp package not installed?)")

# Set by the MCP-mount block further down, before the app actually starts --
# read here as a closure so `lifespan` can be passed to FastAPI() below,
# before the mounted app it needs to enter the lifespan of even exists yet.
_mcp_asgi_app = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # A plain app.mount() does not propagate a mounted sub-app's own
    # lifespan -- FastMCP's Streamable HTTP transport needs its internal
    # session-manager task group started via its lifespan, or every request
    # fails with "Task group is not initialized" (confirmed empirically).
    async with AsyncExitStack() as stack:
        if _mcp_asgi_app is not None:
            await stack.enter_async_context(_mcp_asgi_app.router.lifespan_context(_mcp_asgi_app))
        yield


app = FastAPI(title="Lecture Bot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://perfectpixels.com",
        "https://www.perfectpixels.com",
        # Production frontend (CloudFront + lecturebot.perfectpixels.com). In
        # normal operation CloudFront proxies /api/* same-origin, so the
        # browser never actually needs CORS here — this is a safety net for
        # testing directly against the App Runner URL or the CloudFront
        # default *.cloudfront.net domain before the custom domain is live.
        "https://lecturebot.perfectpixels.com",
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
CHAT_MAX_MESSAGE_CHARS = int(os.environ.get("CHAT_MAX_MESSAGE_CHARS", "8000"))
RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "30"))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))
CHAT_MAX_RESULTS = int(os.environ.get("CHAT_MAX_RESULTS", "6"))
FEEDBACK_INTENT_TIMEOUT_SECONDS = float(os.environ.get("FEEDBACK_INTENT_TIMEOUT_SECONDS", "8"))
FEEDBACK_FIRST_TOKEN_TIMEOUT_SECONDS = float(
    os.environ.get("FEEDBACK_FIRST_TOKEN_TIMEOUT_SECONDS", "15")
)
FEEDBACK_STREAM_TIMEOUT_SECONDS = float(os.environ.get("FEEDBACK_STREAM_TIMEOUT_SECONDS", "90"))
EXPLORE_TIMEOUT_SECONDS = float(os.environ.get("EXPLORE_TIMEOUT_SECONDS", "30"))
EXPLORE_MAX_RESULTS = int(os.environ.get("EXPLORE_MAX_RESULTS", "6"))
BOARD_MAX_TITLE_CHARS = int(os.environ.get("BOARD_MAX_TITLE_CHARS", "200"))
# Single active course for the homework-help feature (see canvas_assignments.py).
# Reuses CANVAS_COURSE_IDS (the same comma-separated var scripts/canvas_sync.py
# reads for bulk KB ingestion) rather than a second, parallel var — this
# feature just takes the first course in that list as "the active course."
_CANVAS_COURSE_IDS = [
    cid.strip()
    for cid in os.environ.get("CANVAS_COURSE_IDS", "").split(",")
    if cid.strip()
]
CANVAS_COURSE_ID = _CANVAS_COURSE_IDS[0] if _CANVAS_COURSE_IDS else "1916689"
MCP_API_KEY = os.environ.get("MCP_API_KEY", "")

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
    assignment_id: Optional[int] = Field(
        default=None,
        description="When set, grounds the answer in this Canvas assignment's rubric/description (homework-help mode).",
    )


class ChatResponse(BaseModel):
    answer: str
    audio_base64: Optional[str] = None
    sources: List[str] = []
    relevant_concepts: List[str] = []
    suggested_projects: List[Dict[str, str]] = []


def _raw_bot():
    """The raw FastPersonaBot instance, bypassing the CachedPersonaBot wrapper
    (which only proxies a fixed set of methods). Returns None if the
    initialized bot isn't a FastPersonaBot (e.g. a fallback bot without the
    private retrieval methods explore/feedback need)."""
    candidate = getattr(bot, "bot", bot)
    if candidate is not None and hasattr(candidate, "_retrieve_parallel"):
        return candidate
    return None


# Mounted at /api/mcp so it rides the existing App Runner service + the
# existing CloudFront /api/* cache behavior -- no new infra. Fail closed: an
# unset MCP_API_KEY means the mount is skipped entirely rather than served
# unauthenticated.
if HAS_MCP:
    if MCP_API_KEY:
        try:
            _mcp_asgi_app = mcp_server.build_authenticated_mcp_app(
                _raw_bot, MCP_API_KEY, check_rate_limit=_check_rate_limit
            )
            app.mount("/api/mcp", _mcp_asgi_app)
            print("✓ MCP server mounted at /api/mcp")
        except Exception as e:
            print(f"Error initializing MCP server: {e}")
    else:
        print("⚠ MCP_API_KEY not set -- /api/mcp will not be mounted")


async def _feedback_sse_generator(feedback_bot, message: str, lang: str):
    """Bridges feedback_mode.run_feedback_stream (a sync generator making
    blocking boto3 calls) onto an async SSE response: runs the generator in a
    background thread, pushes each event onto an asyncio.Queue via
    call_soon_threadsafe, and awaits the queue here."""
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()
    _SENTINEL = object()

    def _produce():
        try:
            for event in run_feedback_stream(feedback_bot, message, response_language=lang):
                loop.call_soon_threadsafe(queue.put_nowait, event)
        except Exception as e:
            print(f"⚠ Feedback stream generation failed: {e}")
            loop.call_soon_threadsafe(
                queue.put_nowait, {"type": "error", "message": "Feedback generation failed"}
            )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)

    threading.Thread(target=_produce, daemon=True).start()

    start = time.time()
    got_first_token = False
    while True:
        deadline = (
            FEEDBACK_FIRST_TOKEN_TIMEOUT_SECONDS if not got_first_token else FEEDBACK_STREAM_TIMEOUT_SECONDS
        )
        wait_for = deadline - (time.time() - start)
        if wait_for <= 0:
            yield f"data: {json.dumps({'type': 'error', 'message': 'response truncated -- took too long'})}\n\n"
            return
        try:
            item = await asyncio.wait_for(queue.get(), timeout=wait_for)
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'type': 'error', 'message': 'response truncated -- took too long'})}\n\n"
            return
        if item is _SENTINEL:
            return
        if item.get("type") == "delta":
            got_first_token = True
        yield f"data: {json.dumps(item)}\n\n"
        if item.get("type") in ("done", "error"):
            return


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
    if len(message) > CHAT_MAX_MESSAGE_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Message too long (max {CHAT_MAX_MESSAGE_CHARS} characters)",
        )

    lang = request.response_language if request.response_language in ("en", "zh") else "en"

    # Homework-help (assignment_id set) always stays on the existing blocking
    # concept path -- classification is skipped entirely for it.
    intent = "concept"
    if HAS_FEEDBACK and not request.assignment_id:
        feedback_bot = _raw_bot()
        if feedback_bot:
            try:
                intent = await asyncio.wait_for(
                    run_in_threadpool(classify_intent, feedback_bot, message),
                    timeout=FEEDBACK_INTENT_TIMEOUT_SECONDS,
                )
            except Exception as e:
                print(f"⚠ Intent classification failed, defaulting to concept: {e}")
                intent = "concept"

    if intent == "feedback":
        if not _check_rate_limit(f"{client_id}:feedback"):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please wait a moment before trying again.",
            )
        feedback_bot = _raw_bot()
        return StreamingResponse(
            _feedback_sse_generator(feedback_bot, message, lang),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:

        def _run_query():
            query_text = message
            if request.assignment_id and HAS_CANVAS:
                try:
                    assignment = get_assignment_by_id(CANVAS_COURSE_ID, request.assignment_id)
                    if assignment:
                        query_text = build_homework_help_prompt(assignment, message, lang)
                except Exception as e:
                    print(f"⚠ Homework-help grounding failed, falling back to plain chat: {e}")
            try:
                return bot.query(
                    query_text,
                    CHAT_MAX_RESULTS,
                    True,
                    response_language=lang,
                )
            except TypeError:
                return bot.query(query_text, CHAT_MAX_RESULTS, True)

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


class AssignmentSummary(BaseModel):
    id: int
    name: str
    due_display: str
    points: float = 0
    html_url: str = ""


@app.get("/api/assignments/upcoming")
async def upcoming_assignments():
    if not HAS_CANVAS:
        return {"assignments": []}
    try:
        results = await run_in_threadpool(get_next_due_assignments, CANVAS_COURSE_ID)
    except Exception as e:
        print(f"⚠ Canvas fetch failed: {e}")
        return {"assignments": []}
    return {
        "assignments": [
            AssignmentSummary(
                id=a["id"],
                name=a["name"],
                due_display=a["due_display"],
                points=a.get("points") or 0,
                html_url=a.get("html_url", ""),
            )
            for a in results
        ]
    }


class ExploreRequest(BaseModel):
    topic: str
    parent_path: List[str] = []
    allow_general_fallback: bool = True
    skip_clarify: bool = False


class ExploreCitation(BaseModel):
    label: str = ""
    excerpt: str = ""
    snippet_index: Optional[int] = None
    location_hint: Optional[str] = None


class ExploreCard(BaseModel):
    id: str
    title: str
    paragraph: str
    concepts: List[str] = []
    grounded: bool
    citations: List[ExploreCitation] = []
    source_note: str


class ExploreResponse(BaseModel):
    mode: str
    topic: str
    parent_path: List[str] = []
    cards: Optional[List[ExploreCard]] = None
    grounded: Optional[bool] = None
    summary: Optional[str] = None
    options: Optional[List[str]] = None
    retrieval: Dict[str, Any] = {}


@app.post("/api/explore", response_model=ExploreResponse)
async def explore(request: ExploreRequest, http_request: Request):
    explore_bot = _raw_bot() if HAS_EXPLORE else None
    if not explore_bot:
        raise HTTPException(status_code=503, detail="Explore is not available")

    client_id = _client_id_from_request(http_request)
    if not _check_rate_limit(f"{client_id}:explore"):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait a moment before trying again.",
        )

    topic = request.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic cannot be empty")
    if len(topic) > 300:
        raise HTTPException(status_code=400, detail="Topic too long (max 300 characters)")

    parent_path = [str(p).strip()[:200] for p in request.parent_path[:8] if str(p).strip()]

    try:
        result = await asyncio.wait_for(
            run_in_threadpool(
                explore_topic.run_explore,
                explore_bot,
                topic,
                parent_path,
                request.allow_general_fallback,
                request.skip_clarify,
                EXPLORE_MAX_RESULTS,
            ),
            timeout=EXPLORE_TIMEOUT_SECONDS,
        )
        return ExploreResponse(**result)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Explore request timed out after {EXPLORE_TIMEOUT_SECONDS:.0f}s",
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Internal explore processing error")


class BoardCreateRequest(BaseModel):
    title: str = "Untitled board"
    data: Dict[str, Any]


class BoardSummary(BaseModel):
    board_id: str
    title: str
    created_at: str
    updated_at: str


class BoardCreateResponse(BaseModel):
    board: BoardSummary
    owner_token: str


class BoardDetail(BoardSummary):
    data: Dict[str, Any]


class BoardSaveRequest(BaseModel):
    owner_token: str
    title: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class BoardDeleteRequest(BaseModel):
    owner_token: str


def _require_boards():
    if not HAS_BOARDS:
        raise HTTPException(status_code=503, detail="Boards are not available")


@app.post("/api/boards", response_model=BoardCreateResponse, status_code=201)
async def create_board(request: BoardCreateRequest, http_request: Request):
    _require_boards()
    client_id = _client_id_from_request(http_request)
    if not _check_rate_limit(f"{client_id}:boards"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait a moment before trying again.")

    title = (request.title or "Untitled board").strip()[:BOARD_MAX_TITLE_CHARS]
    try:
        result = await run_in_threadpool(boards_store.create_board, title=title, data=request.data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Could not create board")
    return BoardCreateResponse(**result)


@app.get("/api/boards/{board_id}")
async def get_board(board_id: str):
    _require_boards()
    board = await run_in_threadpool(boards_store.get_board, board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    return {"board": board}


@app.get("/api/boards")
async def list_boards():
    _require_boards()
    boards = await run_in_threadpool(boards_store.list_boards)
    return {"boards": boards}


@app.post("/api/boards/{board_id}/save")
async def save_board(board_id: str, request: BoardSaveRequest, http_request: Request):
    _require_boards()
    client_id = _client_id_from_request(http_request)
    if not _check_rate_limit(f"{client_id}:boards"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait a moment before trying again.")

    title = request.title.strip()[:BOARD_MAX_TITLE_CHARS] if request.title is not None else None
    try:
        result = await run_in_threadpool(
            boards_store.update_board,
            board_id,
            owner_token=request.owner_token,
            title=title,
            data=request.data,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Could not save board")
    if result is None:
        raise HTTPException(status_code=403, detail="Not authorized to modify this board")
    return {"board": result}


@app.post("/api/boards/{board_id}/delete")
async def delete_board(board_id: str, request: BoardDeleteRequest, http_request: Request):
    _require_boards()
    client_id = _client_id_from_request(http_request)
    if not _check_rate_limit(f"{client_id}:boards"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait a moment before trying again.")

    try:
        deleted = await run_in_threadpool(boards_store.delete_board, board_id, owner_token=request.owner_token)
    except Exception:
        raise HTTPException(status_code=500, detail="Could not delete board")
    if not deleted:
        raise HTTPException(status_code=403, detail="Not authorized to modify this board")
    return {"deleted": True}


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
