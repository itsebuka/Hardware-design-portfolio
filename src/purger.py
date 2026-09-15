"""
X-Purger Core Engine
Orchestrates fetching, filtering, and bulk-deleting tweets + bookmarks.

Filters:
  - Date range (start_date → end_date)
  - Minimum likes threshold (keeps posts AT or ABOVE min_likes)
  - Post type (tweets, replies, or both)

Supports:
  - Dry-run mode (preview only, no deletions)
  - Checkpointing (resumes from last processed position)
  - Bookmark clearing (all or by date range)
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from src.x_client import XClient, parse_tweet_date

log = logging.getLogger(__name__)

CHECKPOINT_FILE = Path("purger_checkpoint.json")


def load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        try:
            return json.loads(CHECKPOINT_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {"tweet_cursor": None, "deleted_ids": [], "bookmark_cursor": None}


def save_checkpoint(data: dict):
    CHECKPOINT_FILE.write_text(json.dumps(data, indent=2))


class PurgeStats:
    def __init__(self):
        self.deleted    = 0
        self.kept       = 0
        self.skipped    = 0
        self.errors     = 0
        self.bookmarks_deleted = 0
        self.bookmarks_kept    = 0

    def report(self) -> str:
        return (
            f"\n{'='*50}\n"
            f"  📊 PURGE SUMMARY\n"
            f"{'='*50}\n"
            f"  🗑️  Tweets deleted      : {self.deleted}\n"
            f"  💛 Tweets kept (liked)  : {self.kept}\n"
            f"  ⏭️  Out of range skipped : {self.skipped}\n"
            f"  ❌ Errors               : {self.errors}\n"
            f"  🔖 Bookmarks deleted    : {self.bookmarks_deleted}\n"
            f"  🔖 Bookmarks kept       : {self.bookmarks_kept}\n"
            f"{'='*50}"
        )


def purge_tweets(
    client: XClient,
    start_date: datetime,
    end_date: datetime,
    min_likes: int = 2,
    dry_run: bool = False,
    max_deletions: int = 500,
    inter_delete_delay: float = 1.2,
) -> PurgeStats:
    """
    Fetch and delete tweets/replies in the given date range
    that have fewer than min_likes likes.

    max_deletions caps how many are deleted per run (for GitHub Actions safety).
    """
    stats      = PurgeStats()
    checkpoint = load_checkpoint()
    cursor     = checkpoint.get("tweet_cursor")
    already_deleted = set(checkpoint.get("deleted_ids", []))

    # Normalize dates to UTC
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)

    log.info(f"🐦 @{client.username} | Range: {start_date.date()} → {end_date.date()} | Min likes to keep: {min_likes}")
    log.info(f"{'[DRY RUN] ' if dry_run else ''}Starting tweet purge...")

    pages_exhausted = False

    while stats.deleted < max_deletions and not pages_exhausted:
        try:
            tweets, next_cursor = client.fetch_tweets_page(cursor)
        except Exception as e:
            log.error(f"Failed to fetch timeline page: {e}")
            break

        if not tweets:
            log.info("No more tweets to fetch — timeline exhausted.")
            pages_exhausted = True
            checkpoint["tweet_cursor"] = None  # Reset for next run
            save_checkpoint(checkpoint)
            break

        oldest_on_page = None

        for tweet in tweets:
            if stats.deleted >= max_deletions:
                log.info(f"Reached max deletions per run ({max_deletions}). Stopping.")
                break

            tweet_id   = tweet.get("id")
            tweet_date = parse_tweet_date(tweet.get("created_at"))
            likes      = tweet.get("likes", 0)

            if not tweet_id or not tweet_date:
                stats.skipped += 1
                continue

            if oldest_on_page is None or tweet_date < oldest_on_page:
                oldest_on_page = tweet_date

            # ── Date range filter ──
            if tweet_date > end_date:
                stats.skipped += 1
                continue

            if tweet_date < start_date:
                # We've scrolled past our target range
                log.info(f"Passed start date ({tweet_date.date()} < {start_date.date()}). Done with range.")
                pages_exhausted = True
                checkpoint["tweet_cursor"] = None
                save_checkpoint(checkpoint)
                break

            # ── Already processed ──
            if tweet_id in already_deleted:
                continue

            # ── Likes filter — KEEP posts with min_likes or more ──
            if likes >= min_likes:
                stats.kept += 1
                log.info(f"  💛 KEEPING  [{tweet_date.date()}] id={tweet_id} likes={likes}  \"{tweet['text'][:60]}\"")
                continue

            # ── Delete ──
            log.info(f"  🗑️  DELETING [{tweet_date.date()}] id={tweet_id} likes={likes}  \"{tweet['text'][:60]}\"")

            if not dry_run:
                success = client.delete_tweet(tweet_id)
                if success:
                    stats.deleted += 1
                    already_deleted.add(tweet_id)
                    checkpoint["deleted_ids"] = list(already_deleted)
                    checkpoint["tweet_cursor"] = next_cursor
                    save_checkpoint(checkpoint)
                    time.sleep(inter_delete_delay + (0.3 * (stats.deleted % 5 == 0)))
                else:
                    stats.errors += 1
                    log.warning(f"  ⚠️  Failed to delete {tweet_id}")
            else:
                stats.deleted += 1  # Count in dry run too

        if not pages_exhausted:
            cursor = next_cursor
            checkpoint["tweet_cursor"] = cursor
            save_checkpoint(checkpoint)

            if next_cursor is None:
                log.info("Reached end of timeline.")
                pages_exhausted = True

        # Brief pause between pages
        time.sleep(2)

    return stats


def purge_bookmarks(
    client: XClient,
    dry_run: bool = False,
    max_deletions: int = 500,
) -> PurgeStats:
    """
    Clear all bookmarks. First tries the native 'clear all' endpoint,
    falls back to deleting one-by-one if that fails.
    """
    stats = PurgeStats()

    log.info(f"🔖 Starting bookmark purge... {'[DRY RUN]' if dry_run else ''}")

    # Try bulk clear first
    if not dry_run:
        log.info("Attempting native 'Clear all bookmarks'...")
        if client.delete_all_bookmarks():
            log.info("✅ All bookmarks cleared via native endpoint!")
            stats.bookmarks_deleted = -1  # Signal bulk delete
            return stats
        log.info("Bulk clear unavailable, falling back to individual deletion...")

    # Individual deletion
    checkpoint = load_checkpoint()
    cursor     = checkpoint.get("bookmark_cursor")

    while stats.bookmarks_deleted < max_deletions:
        try:
            bookmarks, next_cursor = client.fetch_bookmarks_page(cursor)
        except Exception as e:
            log.error(f"Failed to fetch bookmarks: {e}")
            break

        if not bookmarks:
            log.info("No more bookmarks.")
            checkpoint["bookmark_cursor"] = None
            save_checkpoint(checkpoint)
            break

        for bm in bookmarks:
            if stats.bookmarks_deleted >= max_deletions:
                break

            bm_id = bm.get("id")
            if not bm_id:
                continue

            log.info(f"  🔖 Removing bookmark id={bm_id}  \"{bm.get('text', '')[:60]}\"")

            if not dry_run:
                success = client.delete_bookmark(bm_id)
                if success:
                    stats.bookmarks_deleted += 1
                    time.sleep(0.8)
                else:
                    stats.bookmarks_kept += 1
            else:
                stats.bookmarks_deleted += 1

        cursor = next_cursor
        checkpoint["bookmark_cursor"] = cursor
        save_checkpoint(checkpoint)

        if next_cursor is None:
            break

        time.sleep(2)

    return stats
