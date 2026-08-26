"""
MCP (Model Context Protocol) HTTP server — protocol/transport wiring only.
Business logic lives in src/mcp_tools.py; this module just registers that
logic as MCP tools and produces a mountable ASGI app.

Exposes two tools over Streamable HTTP, mounted onto the existing FastAPI
app at /api/mcp (api/main.py) so it rides the same App Runner service and
CloudFront /api/* routing as everything else — no new infra.

Auth is a simple shared-secret bearer token (MCP_API_KEY), checked by a
small ASGI middleware wrapping just this mounted sub-app. Every other route
in api/main.py is intentionally untouched by this — this endpoint is the
only one that requires a credential.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Optional

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

MCP_API_KEY = os.environ.get("MCP_API_KEY", "")


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Rejects any request to the wrapped app that doesn't carry
    `Authorization: Bearer <MCP_API_KEY>`. Scoped to the MCP sub-app only —
    never attached to the main FastAPI app, which stays unauthenticated on
    every other route exactly as it is today."""

    def __init__(self, app, expected_key: str):
        super().__init__(app)
        self.expected_key = expected_key

    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {self.expected_key}":
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Applies api/main.py's existing rate-limit bucket machinery to the MCP
    mount, under a fixed namespace (bearer-token-gated, not per-browser, so
    one shared bucket for now rather than per-client)."""

    def __init__(self, app, check_rate_limit: Callable[[str], bool], namespace: str = "mcp"):
        super().__init__(app)
        self.check_rate_limit = check_rate_limit
        self.namespace = namespace

    async def dispatch(self, request: Request, call_next):
        if not self.check_rate_limit(self.namespace):
            return JSONResponse({"error": "rate limit exceeded"}, status_code=429)
        return await call_next(request)


def build_mcp_asgi_app(get_raw_bot: Callable[[], Optional[Any]]) -> Starlette:
    """get_raw_bot: zero-arg callable returning the raw FastPersonaBot (e.g.
    api/main.py's _raw_bot), or None if unavailable. Called per-request, not
    once at import time, since bot initialization can fail independently."""
    from mcp.server.mcpserver import MCPServer
    from mcp.server.transport_security import TransportSecuritySettings

    import mcp_tools  # sibling module in src/, already on sys.path via api/main.py's insert

    mcp_server: MCPServer = MCPServer("lecture-bot-mcp")

    @mcp_server.tool()
    def retrieve_lectures(
        query: str,
        layer: Optional[str] = None,
        doc_type: Optional[str] = None,
        max_results: int = 6,
    ) -> dict:
        """Raw retrieval from the UX/design-thinking knowledge base.

        layer: omit for normal ranked retrieval across everything;
          "directive" = grading rubrics and course policy ONLY (what governs
          a grade); "reference" = all other course material.

        doc_type: narrow further by kind of material --
          "lecture"     lecture and talk transcripts (the bulk of the corpus)
          "assignment"  assignment briefs
          "rubric"      grading rubrics
          "course-policy" the course grading policy
          "case-study"  professional project case studies
          "portfolio"   agency/portfolio material
          "cv"          the instructor's professional background
          "framework"   agentic-AI operating model and design frameworks
          "meta"        repo/build documentation -- not course content

        The two combine. Use doc_type to keep bio material ("cv",
        "portfolio") out of a subject-matter answer, or to target it
        deliberately when the question really is about background."""
        bot = get_raw_bot()
        if bot is None:
            return {"error": "bot not initialized"}
        return mcp_tools.mcp_retrieve(
            bot, query, layer=layer, doc_type=doc_type, max_results=max_results
        )

    @mcp_server.tool()
    def ask_professor(question: str, response_language: str = "en") -> dict:
        """Ask the course knowledge base a question and get a composed answer
        in the instructor's teaching voice, with the student-facing guardrails
        applied — the same behaviour as the web chat.

        Prefer this over retrieve_lectures for any question you actually want
        answered. retrieve_lectures returns raw chunks and leaves synthesis to
        the caller, which means the answer arrives in the caller's voice with
        none of the course guardrails; use it when you specifically want source
        passages to inspect or quote.

        Differs from generate_methodology, which is deliberately neutral and
        third-person: this one stays in persona and will not produce a
        student's deliverable for them.
        response_language: "en" or "zh" (Simplified Chinese)."""
        bot = get_raw_bot()
        if bot is None:
            return {"error": "bot not initialized"}
        return mcp_tools.mcp_ask(bot, question, response_language=response_language)

    @mcp_server.tool()
    def generate_methodology(request: str, response_language: str = "en") -> dict:
        """Ungated UX / design-thinking / AI-product methodology guidance,
        grounded in the lecture knowledge base. Neutral third-person
        reference output, not a teaching persona -- for orchestrators/agents
        that want synthesized guidance rather than raw source chunks.
        response_language: "en" or "zh" (Simplified Chinese)."""
        bot = get_raw_bot()
        if bot is None:
            return {"error": "bot not initialized"}
        return mcp_tools.mcp_methodology(bot, request, response_language=response_language)

    @mcp_server.tool()
    def list_rubrics() -> dict:
        """List the assignment rubrics available in the instructor grading
        handbook. Use this to discover valid `assignment` values for
        get_rubric and grade_submission."""
        return mcp_tools.mcp_list_rubrics()

    @mcp_server.tool()
    def get_rubric(assignment: str) -> dict:
        """Full grading rubric for one assignment, including its Instructor
        Evaluation Checklist, annotated strong/weak examples, and the decision
        tree that maps work quality to a score band. `assignment` accepts loose
        names ("persona", "wireframes", "Assignment 6")."""
        return mcp_tools.mcp_get_rubric(assignment)

    @mcp_server.tool()
    def grade_submission(submission: str, assignment: str) -> dict:
        """INSTRUCTOR TOOL. Assess a student's submission against the course
        grading handbook and return per-criterion findings, a suggested score
        on the handbook's 0-4.0 scale, the decision-tree branch it matched, and
        draft feedback for the student.

        Output is a DRAFT for the instructor to review and edit -- it is not a
        final grade and must not be handed to a student unreviewed. Returns
        gradable=false rather than guessing when the submission is too short or
        no rubric matches the assignment."""
        bot = get_raw_bot()
        if bot is None:
            return {"error": "bot not initialized"}
        return mcp_tools.mcp_grade(bot, submission, assignment)

    @mcp_server.tool()
    def derive_calibration(submission: str, assignment: str) -> dict:
        """INSTRUCTOR TOOL. Given a submission the instructor scored 4.0, draft
        reusable grading criteria for that assignment: what the 4.0 bar is,
        what separates 4.0 from 3.x, and the failure modes weaker work shows.

        Returns rubric LANGUAGE rather than storing the submission, so
        calibration can be kept without retaining student work. Output is a
        draft to review and edit -- once saved under data/grading/calibration/
        it shapes every later grade for that assignment."""
        bot = get_raw_bot()
        if bot is None:
            return {"error": "bot not initialized"}
        return mcp_tools.mcp_derive_calibration(bot, submission, assignment)

    @mcp_server.tool()
    def review_document(document: str, focus: str = "") -> dict:
        """INSTRUCTOR TOOL. Check the instructor's OWN draft (a lecture, syllabus,
        assignment brief, case study) against their own course material.

        Reports contradictions with what the lectures/rubrics actually say,
        claims the material doesn't support, and relevant material the draft
        omits -- each tied to a retrieved source.

        Scope is consistency and coverage ONLY. It deliberately does not assess
        structure, clarity, tone or style: the knowledge base is lecture and
        rubric content and cannot ground that kind of feedback.

        For a STUDENT's work use the student-facing feedback path instead --
        that carries the never-do-their-work rule, which this tool does not.

        focus: optional, what to check in particular (e.g. "does this match
        what I taught about journey mapping?")."""
        bot = get_raw_bot()
        if bot is None:
            return {"error": "bot not initialized"}
        return mcp_tools.mcp_review_document(bot, document, focus=focus)

    @mcp_server.tool()
    def check_authorship_signals(
        document: str,
        assignment_brief: str = "",
        prior_artifacts: str = "",
        style_trigger: float = 0.40,
    ) -> dict:
        """INSTRUCTOR TOOL. Gather evidence about how a submission was produced,
        for the instructor to review before talking to the student.

        This does NOT determine authorship and never says a document was
        AI-generated. It returns findings across tiers:
          tier1  verifiable -- fabricated citations, untraceable external
                 statistics, claims misattributed to real sources
          tier3  substance -- missing required specifics, internal
                 contradictions, contradictions with the student's prior work
          tier4  leakage -- prompt residue, unrendered markdown
          style  register/formatting habits -- CORROBORATING ONLY

        outcome is NO_SIGNAL, STYLE_ONLY_INSUFFICIENT, or INVESTIGATE.
        Style can never produce INVESTIGATE on its own however many tells
        fire: those tells also describe formal academic writing and misfire
        disproportionately on students who learned English academically.

        Supply assignment_brief to enable the missing-specifics check (without
        it that check is disabled rather than guessing at requirements), and
        prior_artifacts to enable continuity checking against the student's
        own earlier work -- the strongest substance signal available.

        Tier 2 (document version history, submission telemetry) is the
        strongest evidence class and cannot be seen from text; the result
        lists what to check yourself."""
        bot = get_raw_bot()
        if bot is None:
            return {"error": "bot not initialized"}
        return mcp_tools.mcp_check_authorship(
            bot,
            document,
            assignment_brief=assignment_brief,
            prior_artifacts=prior_artifacts,
            style_trigger=style_trigger,
        )

    @mcp_server.tool()
    def calibrate_authorship(documents: list[str]) -> dict:
        """INSTRUCTOR TOOL. Measure the style tells' false-positive rate against
        writing you know a human produced (pre-2022 submissions are ideal).

        Every document supplied is treated as known-human, so any threshold it
        trips is by construction a false positive. Returns the false-positive
        rate at each candidate threshold plus a per-tell misfire rate -- a tell
        that fires on most of your students' real writing carries no
        information and should be dropped or re-thresholded.

        Use this to choose style_trigger from evidence rather than a priori."""
        return mcp_tools.mcp_calibrate_authorship(documents)

    # Mount path is "/" here because this whole app is itself mounted at
    # /api/mcp by api/main.py -- the sub-app only ever sees paths relative
    # to that mount point, so its own route table should start at "/".
    #
    # transport_security: the mcp SDK's streamable_http_app() auto-enables
    # DNS-rebinding Host-header validation whenever its own `host` config
    # param is "127.0.0.1" (its default) -- which we never override, since
    # we don't use it to bind a socket (we mount this Starlette app inside
    # our own FastAPI app instead). That auto-enable only allow-lists
    # 127.0.0.1/localhost/::1, so every request against the real deployed
    # hostname gets rejected with 421 "Invalid Host header" -- confirmed by
    # reading mcp/server/lowlevel/server.py's streamable_http_app(). Explicitly
    # disabling it here is correct, not just a workaround: BearerAuthMiddleware
    # above already gates this endpoint, and Host-header allow-listing would
    # need per-environment config anyway (App Runner's default hostname today,
    # a custom domain later) for no real security benefit over the bearer token.
    transport_security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    return mcp_server.streamable_http_app(streamable_http_path="/", transport_security=transport_security)


def build_url_token_mcp_app(
    get_raw_bot: Callable[[], Optional[Any]],
    check_rate_limit: Optional[Callable[[str], bool]] = None,
) -> Starlette:
    """MCP app with NO header auth, intended to be mounted beneath an
    unguessable path segment so the URL itself is the credential.

    This exists because claude.ai's "Add custom connector" dialog accepts only
    a URL and optional OAuth client credentials -- there is no custom-header
    field, so a bearer token cannot be supplied there.

    The tradeoff is real and worth stating: URLs are logged in more places
    than headers (browser history, proxy and access logs, the connector
    settings screen), so this credential is more exposed than the header one.
    It therefore uses its OWN token, separate from MCP_API_KEY, so that a
    leaked URL does not also compromise the header-authenticated endpoint and
    can be rotated on its own. Rate limiting still applies.
    """
    inner = build_mcp_asgi_app(get_raw_bot)
    if check_rate_limit is not None:
        inner.add_middleware(RateLimitMiddleware, check_rate_limit=check_rate_limit, namespace="mcp-url")
    return inner


def build_authenticated_mcp_app(
    get_raw_bot: Callable[[], Optional[Any]],
    api_key: str,
    check_rate_limit: Optional[Callable[[str], bool]] = None,
) -> Starlette:
    """Convenience wrapper: builds the MCP app and wraps it with bearer auth
    (and, if provided, rate limiting) in one call. api_key must be non-empty
    -- callers should not mount an MCP app with an empty key (fail closed,
    checked by the caller)."""
    inner = build_mcp_asgi_app(get_raw_bot)
    if check_rate_limit is not None:
        inner.add_middleware(RateLimitMiddleware, check_rate_limit=check_rate_limit)
    inner.add_middleware(BearerAuthMiddleware, expected_key=api_key)
    return inner
