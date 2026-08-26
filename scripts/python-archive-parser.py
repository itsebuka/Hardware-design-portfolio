"""
Twitter/X Archive Parser - Enhanced
Extracts Tweet/Reply/Repost/Like IDs from a downloaded Twitter archive.

Supports:
  - tweet.js / tweets.js / tweets-part*.js
  - like.js
  - Raw .zip Twitter archive files
  - Filtering by date range, type, keywords, min engagement

Usage:
  python archive_parser.py [options]

  --archive     Path to tweet.js, tweets.js, like.js or archive.zip
                (default: tweet.js)
  --start-date  Start date YYYY-MM-DD (default: no limit)
  --end-date    End date YYYY-MM-DD   (default: no limit)
  --type        Filter type: tweets, replies, reposts, likes, all
                (default: all)
  --keyword     Only include tweets containing this word (optional)
  --min-likes   Skip tweets with >= N likes (protect popular posts) (default: 0)
  --output      Output filename for extracted IDs (default: filtered_ids.txt)
  --stats       Show summary statistics after parsing
"""

import json
import re
import sys
import zipfile
import argparse
from pathlib import Path
from datetime import datetime, timezone


# ── Helpers ─────────────────────────────────────────────────────────────────

def strip_js_assignment(content: str) -> str:
    """Remove the window.YTD.* variable prefix Twitter adds to their .js files."""
    cleaned = re.sub(r"^window\.YTD\.\w+\.part\d*\s*=\s*", "", content.strip())
    return cleaned


def parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def tweet_date(tweet: dict) -> datetime | None:
    """Parse the created_at field from a tweet entry."""
    raw = tweet.get("created_at")
    if not raw:
        return None
    try:
        # Format: "Wed May 20 14:02:00 +0000 2026"
        return datetime.strptime(raw, "%a %b %d %H:%M:%S %z %Y")
    except ValueError:
        return None


def is_reply(tweet: dict) -> bool:
    """Detect if a tweet is a reply (has in_reply_to_status_id_str set)."""
    return bool(tweet.get("in_reply_to_status_id_str"))


def is_repost(tweet: dict) -> bool:
    """Detect if a tweet is a retweet (starts with 'RT @')."""
    text = tweet.get("full_text", tweet.get("text", ""))
    return text.strip().startswith("RT @")


# ── Loaders ──────────────────────────────────────────────────────────────────

def load_js_file(path: Path) -> list[dict]:
    """Load a .js Twitter archive file (tweet.js, like.js, etc.)."""
    content = path.read_text(encoding="utf-8")
    json_str = strip_js_assignment(content)
    return json.loads(json_str)


def load_from_zip(zip_path: Path, target: str = "tweet") -> list[dict]:
    """
    Extract tweet/like data from a Twitter archive .zip.
    target: 'tweet' or 'like'
    """
    entries = []
    pattern = re.compile(rf"data/{target}s?(?:-part\d+)?\.js", re.IGNORECASE)

    with zipfile.ZipFile(zip_path, "r") as zf:
        matched = [name for name in zf.namelist() if pattern.search(name)]
        if not matched:
            raise FileNotFoundError(
                f"No {target}.js file found in the archive. "
                f"Available files: {zf.namelist()[:20]}"
            )
        for name in matched:
            content = zf.read(name).decode("utf-8")
            json_str = strip_js_assignment(content)
            entries.extend(json.loads(json_str))

    return entries


def load_archive(archive_path: str, data_type: str) -> list[dict]:
    """Load the archive and return raw entries list."""
    p = Path(archive_path)
    if not p.exists():
        print(f"[!] Error: File not found: {p}", file=sys.stderr)
        sys.exit(1)

    if p.suffix.lower() == ".zip":
        target = "like" if data_type == "likes" else "tweet"
        return load_from_zip(p, target=target)
    else:
        return load_js_file(p)


# ── Core Filter ───────────────────────────────────────────────────────────────

def filter_entries(
    entries: list[dict],
    data_type: str,
    start_date: datetime | None,
    end_date: datetime | None,
    keyword: str | None,
    min_likes: int,
) -> tuple[list[str], dict]:
    """
    Filter archive entries and return matched IDs + stats.

    Returns:
        matched_ids: list of ID strings
        stats: dict of stats (total, matched, by_type)
    """
    matched_ids = []
    stats = {
        "total_entries": len(entries),
        "matched": 0,
        "skipped_date": 0,
        "skipped_type": 0,
        "skipped_keyword": 0,
        "skipped_min_likes": 0,
        "type_breakdown": {"tweets": 0, "replies": 0, "reposts": 0, "likes": 0},
    }

    for entry in entries:
        # Handle both {tweet: {...}} and flat tweet objects, and like.js format
        if "tweet" in entry:
            tweet = entry["tweet"]
            entry_type = "tweet"
        elif "like" in entry:
            # like.js structure: {like: {tweetId, fullText, expandedUrl}}
            like = entry["like"]
            matched_ids.append(like.get("tweetId"))
            stats["type_breakdown"]["likes"] += 1
            stats["matched"] += 1
            continue
        else:
            tweet = entry
            entry_type = "tweet"

        # ── Date filter ──
        t_date = tweet_date(tweet)
        if start_date and t_date and t_date < start_date:
            stats["skipped_date"] += 1
            continue
        if end_date and t_date and t_date > end_date:
            stats["skipped_date"] += 1
            continue

        # ── Type filter ──
        tweet_is_reply = is_reply(tweet)
        tweet_is_repost = is_repost(tweet)

        if tweet_is_repost:
            actual_type = "reposts"
        elif tweet_is_reply:
            actual_type = "replies"
        else:
            actual_type = "tweets"

        if data_type not in ("all", "likes") and data_type != actual_type:
            stats["skipped_type"] += 1
            continue

        # ── Keyword filter ──
        if keyword:
            text = tweet.get("full_text", tweet.get("text", ""))
            if keyword.lower() not in text.lower():
                stats["skipped_keyword"] += 1
                continue

        # ── Min likes protection ──
        fav_count = int(tweet.get("favorite_count", 0))
        if min_likes > 0 and fav_count >= min_likes:
            stats["skipped_min_likes"] += 1
            continue

        # ── Collect ──
        matched_ids.append(tweet.get("id_str"))
        stats["type_breakdown"][actual_type] += 1
        stats["matched"] += 1

    return matched_ids, stats


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="X/Twitter Archive Parser – Extract tweet IDs for purging."
    )
    parser.add_argument(
        "--archive", default="tweet.js",
        help="Path to tweet.js, like.js, or archive.zip (default: tweet.js)"
    )
    parser.add_argument("--start-date", default=None, help="Filter start date YYYY-MM-DD")
    parser.add_argument("--end-date", default=None, help="Filter end date YYYY-MM-DD")
    parser.add_argument(
        "--type", default="all", dest="data_type",
        choices=["all", "tweets", "replies", "reposts", "likes"],
        help="Type of entries to extract (default: all)"
    )
    parser.add_argument("--keyword", default=None, help="Only include tweets with this keyword")
    parser.add_argument(
        "--min-likes", type=int, default=0,
        help="Skip tweets with >= N likes (to protect popular posts)"
    )
    parser.add_argument("--output", default="filtered_ids.txt", help="Output file for IDs")
    parser.add_argument("--stats", action="store_true", help="Print detailed stats after parsing")
    args = parser.parse_args()

    start_dt = parse_date(args.start_date)
    end_dt = parse_date(args.end_date)
    if end_dt:
        # Make end_date inclusive (end of day)
        end_dt = end_dt.replace(hour=23, minute=59, second=59)

    print(f"[+] Loading archive: {args.archive}")
    entries = load_archive(args.archive, args.data_type)
    print(f"[+] Loaded {len(entries)} raw entries.")

    matched_ids, stats = filter_entries(
        entries,
        data_type=args.data_type,
        start_date=start_dt,
        end_date=end_dt,
        keyword=args.keyword,
        min_likes=args.min_likes,
    )

    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as out:
        for tid in matched_ids:
            if tid:
                out.write(f"{tid}\n")

    print(f"\n[✓] Extraction complete!")
    print(f"    Matched IDs : {stats['matched']}")
    print(f"    Saved to    : {output_path.resolve()}")

    if args.stats or True:  # Always show brief stats
        print(f"\n[Stats]")
        print(f"  Total entries scanned : {stats['total_entries']}")
        print(f"  Skipped (date filter) : {stats['skipped_date']}")
        print(f"  Skipped (type filter) : {stats['skipped_type']}")
        print(f"  Skipped (keyword)     : {stats['skipped_keyword']}")
        print(f"  Skipped (min likes)   : {stats['skipped_min_likes']}")
        print(f"  Type breakdown:")
        for k, v in stats["type_breakdown"].items():
            if v:
                print(f"    {k.capitalize():<12}: {v}")


if __name__ == "__main__":
    main()