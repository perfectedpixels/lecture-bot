# ---------------------------------------------------------------------------
# MIRRORED FILE — canonical copy lives in:
#   ppmg/pythonchatbot-integration/kb/kbpolicy.py
#
# Both repos write to the same Bedrock knowledge base, so both must enforce the
# same publishability rules. Keep this file and policy.yaml in sync with the
# canonical copies; do not diverge them locally.
# ---------------------------------------------------------------------------

"""
Publishability gate for knowledge base ingestion.

The KB backs a public-facing chatbot, so any ingested document can be quoted
verbatim to an anonymous visitor. This module is the mechanical check that runs
before ingestion, replacing "someone remembered to read the file first".

It catches the two failure modes that have actually occurred:
  1. Third-party licensed material (a vendor research note marked
     "restricted to the personal use of the license holder").
  2. Real customer names attached to candid internal commentary.

Designed to be imported by any ingestion pipeline writing to the shared bucket
(this repo and lecture-bot), so both enforce the same rules.

Usage:
    from kbpolicy import Policy
    policy = Policy.load()
    violations = policy.check(text, source="path/to/doc.md", declarations={...})
    if violations:
        # blocking violations refuse the document
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import yaml

DEFAULT_POLICY_PATH = Path(__file__).with_name("policy.yaml")

# How much context to show around a match, so a reviewer can judge a hit
# without opening the file.
_CONTEXT_CHARS = 60


@dataclass(frozen=True)
class Violation:
    """A single policy failure. `blocking` violations refuse ingestion."""

    source: str
    rule: str
    detail: str
    excerpt: str = ""
    blocking: bool = True

    def __str__(self) -> str:
        mark = "BLOCK" if self.blocking else "WARN "
        line = f"[{mark}] {self.source}: {self.rule} — {self.detail}"
        if self.excerpt:
            line += f"\n          …{self.excerpt}…"
        return line


class Policy:
    """Loaded publishability rules."""

    def __init__(self, config: Dict) -> None:
        self.rights_markers: List[str] = [
            m.lower() for m in config.get("rights_markers", [])
        ]
        self.deny_terms: List[str] = config.get("deny_terms", [])
        self.deny_patterns: Dict[str, str] = config.get("deny_patterns", {})
        # Deliberately-public addresses, exempt from the email pattern.
        self.allow_emails = {e.lower() for e in config.get("allow_emails", [])}
        self.required_declarations: List[str] = config.get(
            "required_declarations", []
        )
        self.allow_visibility: List[str] = config.get("allow_visibility", ["public"])
        self.allow_rights: List[str] = config.get("allow_rights", ["original"])

        # Word-boundary matching so "Belleron" doesn't fire on a substring, and
        # so a term can't be smuggled past by casing.
        self._deny_term_res = [
            (t, re.compile(rf"\b{re.escape(t)}\b", re.IGNORECASE))
            for t in self.deny_terms
        ]
        self._deny_pattern_res = {
            name: re.compile(pat, re.IGNORECASE)
            for name, pat in self.deny_patterns.items()
        }

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Policy":
        path = path or DEFAULT_POLICY_PATH
        with open(path, "r", encoding="utf-8") as fh:
            return cls(yaml.safe_load(fh) or {})

    # ---- checks -----------------------------------------------------------

    def check_declarations(
        self, source: str, declarations: Dict[str, str]
    ) -> List[Violation]:
        """Verify a document group declared what it is, and that the values are
        permitted. Refusing undeclared content is what makes the gate
        fail-closed: forgetting to classify blocks, it does not silently pass.
        """
        out: List[Violation] = []
        for field in self.required_declarations:
            if not declarations.get(field):
                out.append(
                    Violation(
                        source=source,
                        rule="missing-declaration",
                        detail=f"'{field}' is not declared in corpus.yaml",
                    )
                )

        visibility = declarations.get("visibility")
        if visibility and visibility not in self.allow_visibility:
            out.append(
                Violation(
                    source=source,
                    rule="visibility-not-publishable",
                    detail=(
                        f"visibility='{visibility}' is not in "
                        f"{self.allow_visibility}"
                    ),
                )
            )

        rights = declarations.get("rights")
        if rights and rights not in self.allow_rights:
            out.append(
                Violation(
                    source=source,
                    rule="rights-not-publishable",
                    detail=f"rights='{rights}' is not in {self.allow_rights}",
                )
            )
        return out

    def check_content(self, text: str, source: str) -> List[Violation]:
        """Scan document text for licensed-material markers, denied names, and
        contact details."""
        out: List[Violation] = []
        lowered = text.lower()

        for marker in self.rights_markers:
            idx = lowered.find(marker)
            if idx != -1:
                out.append(
                    Violation(
                        source=source,
                        rule="third-party-rights-marker",
                        detail=f"contains {marker!r}",
                        excerpt=_excerpt(text, idx, len(marker)),
                    )
                )

        for term, rx in self._deny_term_res:
            m = rx.search(text)
            if m:
                out.append(
                    Violation(
                        source=source,
                        rule="denied-term",
                        detail=f"names {term!r}",
                        excerpt=_excerpt(text, m.start(), len(m.group(0))),
                    )
                )

        for name, rx in self._deny_pattern_res.items():
            for m in rx.finditer(text):
                # Skip addresses explicitly published by the site owner.
                if name == "email" and m.group(0).lower() in self.allow_emails:
                    continue
                out.append(
                    Violation(
                        source=source,
                        rule=f"denied-pattern:{name}",
                        detail=f"matched {m.group(0)!r}",
                        excerpt=_excerpt(text, m.start(), len(m.group(0))),
                    )
                )
                break  # one finding per pattern per document is enough
        return out

    def check(
        self, text: str, source: str, declarations: Dict[str, str]
    ) -> List[Violation]:
        """Full gate: declarations plus content."""
        return self.check_declarations(source, declarations) + self.check_content(
            text, source
        )


def _excerpt(text: str, start: int, length: int) -> str:
    lo = max(0, start - _CONTEXT_CHARS)
    hi = min(len(text), start + length + _CONTEXT_CHARS)
    return " ".join(text[lo:hi].split())


def blocking(violations: Iterable[Violation]) -> List[Violation]:
    return [v for v in violations if v.blocking]
