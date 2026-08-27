#!/usr/bin/env python3
"""
RETIRED. Superseded by ppmg's pythonchatbot-integration/kb/build_corpus.py.

This script scanned the entire S3 bucket and subtracted a hardcoded list of
excluded prefixes. That is fail-open: the default answer to "should this be in
the knowledge base?" was yes, and safety depended on someone having predicted
every prefix that would ever exist in the bucket.

On 2026-08-23 that assumption broke. A `kb-archive/` prefix (a pre-deduplication
backup written by another tool) appeared after this script's exclude list was
written, so the next run ingested 2,942 archived chunks as if they were fresh
sources and produced 5,576 duplicate chunks, undoing a deduplication pass.
Nothing reached the live index only because the sync was caught first.

The replacement, build_corpus.py in the ppmg repo, is an allowlist: it reads corpus.yaml and
resolves only what is declared there, so a new prefix appearing in the bucket
does nothing at all. It also runs every document through a publishability gate
before ingestion, which this script had no concept of.

    cd <ppmg>/pythonchatbot-integration/kb
    python3 build_corpus.py --profile personal            # dry run
    python3 build_corpus.py --profile personal --apply    # write
    python3 verify_corpus.py --profile personal           # drift check

Note: ingesting NEW transcripts is a different job and still belongs to
scripts/ingest_transcripts.py, which is unaffected by this retirement.

This stub exists rather than a deleted file so that a stale runbook or a
shell-history invocation fails loudly with the reason, instead of failing with
"No such file" and tempting someone to restore the old version from git.
"""

import sys

MESSAGE = __doc__.strip()

if __name__ == "__main__":
    print(MESSAGE, file=sys.stderr)
    sys.exit(1)
