#!/usr/bin/env python3
"""
X-Purger | Main Runner
Invoked by GitHub Actions or locally.

Usage:
  python purge_runner.py [--dry-run] [--tweets-only] [--bookmarks-only]

Environment variables (set as GitHub Secrets or in .env):
  X_AUTH_TOKEN   Your X auth_token cookie value
  X_CT0          Your X ct0 cookie value
  START_DATE     Start date YYYY-MM-DD (default: 2025-11-01)
  END_DATE       End date   YYYY-MM-DD (default: 2026-02-28)
  MIN_LIKES      Keep tweets with >= N likes (default: 2)
  MAX_DELETIONS  Max deletions per run (default: 400)
  DRY_RUN        Set to 'true' to preview without deleting
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

# ── Bootstrap path so src/ imports work ──────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from src.x_client import XClient
from src.purger   import purge_tweets, purge_bookmarks

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def parse_date(date_str: str, label: str) -> datetime:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(
            tzinfo=timezone.utc,
            hour=0, minute=0, second=0
        )
    except ValueError:
        log.error(f"Invalid {label} date: '{date_str}'. Use YYYY-MM-DD format.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="X-Purger Automated Runner")
    parser.add_argument("--dry-run",        action="store_true", help="Preview only — no deletions")
    parser.add_argument("--tweets-only",    action="store_true", help="Only purge tweets/replies")
    parser.add_argument("--bookmarks-only", action="store_true", help="Only clear bookmarks")
    args = parser.parse_args()

    # ── Credentials ──────────────────────────────────────────────────────────
    auth_token = env("X_AUTH_TOKEN")
    ct0        = env("X_CT0")

    if not auth_token or not ct0:
        log.error(
            "Missing X_AUTH_TOKEN or X_CT0 environment variables.\n"
            "  Set them as GitHub Secrets or in a local .env file.\n"
            "  See .env.example for instructions."
        )
        sys.exit(1)

    # ── Config ───────────────────────────────────────────────────────────────
    start_date    = parse_date(env("START_DATE", "2025-11-01"), "START_DATE")
    end_date      = parse_date(env("END_DATE",   "2026-02-28"), "END_DATE")
    end_date      = end_date.replace(hour=23, minute=59, second=59)
    min_likes     = int(env("MIN_LIKES",     "2"))
    max_deletions = int(env("MAX_DELETIONS", "400"))
    dry_run       = args.dry_run or env("DRY_RUN", "false").lower() == "true"

    do_tweets    = not args.bookmarks_only
    do_bookmarks = not args.tweets_only

    # ── Announce ─────────────────────────────────────────────────────────────
    log.info("=" * 60)
    log.info("  🐦 X-Purger | Automated Server-Side Purge")
    log.info("=" * 60)
    log.info(f"  Date range   : {start_date.date()} → {end_date.date()}")
    log.info(f"  Keep if likes ≥ {min_likes}")
    log.info(f"  Max deletions : {max_deletions} per run")
    log.info(f"  Mode         : {'DRY RUN (no deletions)' if dry_run else 'LIVE — WILL DELETE'}")
    log.info(f"  Tweets       : {'yes' if do_tweets else 'no'}")
    log.info(f"  Bookmarks    : {'yes' if do_bookmarks else 'no'}")
    log.info("=" * 60)

    # ── Authenticate ─────────────────────────────────────────────────────────
    client = XClient(auth_token=auth_token, ct0=ct0)
    try:
        client.get_me()
    except (PermissionError, ValueError) as e:
        log.error(f"Authentication failed: {e}")
        sys.exit(1)

    total_deleted   = 0
    total_bookmarks = 0
    exit_code       = 0

    # ── Purge tweets + replies ───────────────────────────────────────────────
    if do_tweets:
        log.info("\n── Purging tweets & replies ──")
        try:
            stats = purge_tweets(
                client       = client,
                start_date   = start_date,
                end_date     = end_date,
                min_likes    = min_likes,
                dry_run      = dry_run,
                max_deletions= max_deletions,
            )
            total_deleted = stats.deleted
            log.info(stats.report())
        except Exception as e:
            log.error(f"Tweet purge error: {e}")
            exit_code = 1

    # ── Clear bookmarks ───────────────────────────────────────────────────────
    if do_bookmarks:
        log.info("\n── Clearing bookmarks ──")
        try:
            bm_stats = purge_bookmarks(
                client        = client,
                dry_run       = dry_run,
                max_deletions = max_deletions,
            )
            total_bookmarks = bm_stats.bookmarks_deleted
            log.info(f"  🔖 Bookmarks removed: {total_bookmarks if total_bookmarks != -1 else 'ALL (bulk cleared)'}")
        except Exception as e:
            log.error(f"Bookmark purge error: {e}")
            exit_code = 1

    # ── Final Summary ─────────────────────────────────────────────────────────
    log.info("\n" + "=" * 60)
    log.info(f"  ✅ Run complete!")
    log.info(f"     Tweets deleted   : {total_deleted}")
    log.info(f"     Bookmarks removed: {total_bookmarks if total_bookmarks != -1 else 'ALL'}")
    if dry_run:
        log.info("     ⚠️  DRY RUN — nothing was actually deleted.")
    log.info("=" * 60)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
