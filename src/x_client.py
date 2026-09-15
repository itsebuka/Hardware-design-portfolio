"""
X/Twitter Internal GraphQL API Client
Uses session cookies (auth_token + ct0) — no official API keys needed.

Handles:
  - Authenticated requests with CSRF protection
  - Rate-limit detection and exponential backoff
  - Fetching user timeline (tweets + replies)
  - Deleting tweets
  - Fetching and deleting bookmarks
"""

import time
import random
import logging
from datetime import datetime, timezone

import requests

log = logging.getLogger(__name__)

# ── X Internal GraphQL Query IDs ─────────────────────────────────────────────
# These are X's internal identifiers. Update if X changes them.
QUERY_IDS = {
    "UserTweetsAndReplies": "E4wA9WNMRVlqd3NFOG3M3A",
    "DeleteTweet":          "VaenaFdIv7GRFG3_K9rWfg",
    "Bookmarks":            "uHRM2gTn_SxKGogpTxIEoQ",
    "DeleteBookmark":       "Jd2u4rMr4hBuBEf_5VXhZg",
    "BookmarksAllDelete":   "skiACZKC1GDYli-M8RzEPQ",
}

BASE_URL   = "https://x.com"
API_URL    = "https://x.com/i/api/graphql"

# X's own web app bearer token — required for all internal API calls.
# This is a public, hardcoded token embedded in X's JS bundle.
BEARER_TOKEN = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D"
    "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

# Standard features blob required by X's GraphQL (fairly stable)
TWEET_FEATURES = {
    "rweb_lists_timeline_redesign_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "tweetypie_unmention_optimization_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": False,
    "tweet_awards_web_tipping_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_media_download_video_enabled": False,
    "responsive_web_enhance_cards_enabled": False,
}


class XClient:
    """Authenticated X web client using session cookies."""

    def __init__(self, auth_token: str, ct0: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {BEARER_TOKEN}",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/127.0.0.0 Safari/537.36"
            ),
            "Accept":          "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type":    "application/json",
            "Referer":         "https://x.com/",
            "Origin":          "https://x.com",
            "x-twitter-active-user":     "yes",
            "x-twitter-auth-type":       "OAuth2Session",
            "x-twitter-client-language": "en",
            "x-csrf-token":              ct0,
        })
        self.session.cookies.set("auth_token", auth_token, domain=".x.com")
        self.session.cookies.set("ct0",        ct0,        domain=".x.com")
        self._user_id   = None
        self._username  = None

    # ── Auth & Identity ──────────────────────────────────────────────────────

    def get_me(self) -> dict:
        """Fetch the authenticated user's profile to validate credentials."""
        # v1.1 REST — stable, reliable with bearer token + cookies
        url  = f"{BASE_URL}/i/api/1.1/account/verify_credentials.json"
        resp = self._get(url, params={"include_email": "false", "skip_status": "true"})
        data = resp.json()
        if "id_str" not in data:
            raise ValueError(
                f"Authentication failed. Response: {data}. "
                "Check your X_AUTH_TOKEN and X_CT0 values."
            )
        self._user_id  = data["id_str"]
        self._username = data["screen_name"]
        log.info(f"Authenticated as @{self._username} (ID: {self._user_id})")
        return data

    @property
    def user_id(self) -> str:
        if not self._user_id:
            self.get_me()
        return self._user_id

    @property
    def username(self) -> str:
        if not self._username:
            self.get_me()
        return self._username

    # ── Timeline Fetching ────────────────────────────────────────────────────

    def fetch_tweets_page(self, cursor: str | None = None) -> tuple[list[dict], str | None]:
        """
        Fetch one page of the user's tweets and replies timeline.
        Returns (tweets, next_cursor).
        """
        qid = QUERY_IDS["UserTweetsAndReplies"]
        url = f"{API_URL}/{qid}/UserTweetsAndReplies"

        variables = {
            "userId":                    self.user_id,
            "count":                     100,
            "includePromotedContent":    False,
            "withCommunity":             True,
            "withVoice":                 True,
            "withV2Timeline":            True,
        }
        if cursor:
            variables["cursor"] = cursor

        import json
        params = {
            "variables": json.dumps(variables),
            "features":  json.dumps(TWEET_FEATURES),
        }

        resp = self._get(url, params=params)
        data = resp.json()
        tweets, next_cursor = self._parse_timeline(data)
        return tweets, next_cursor

    def _parse_timeline(self, data: dict) -> tuple[list[dict], str | None]:
        """Extract tweet objects and pagination cursor from GraphQL response."""
        tweets     = []
        next_cursor = None

        try:
            instructions = (
                data.get("data", {})
                    .get("user", {})
                    .get("result", {})
                    .get("timeline_v2", {})
                    .get("timeline", {})
                    .get("instructions", [])
            )
        except AttributeError:
            log.warning("Unexpected timeline structure: %s", str(data)[:300])
            return tweets, None

        for instruction in instructions:
            if instruction.get("type") == "TimelineAddEntries":
                for entry in instruction.get("entries", []):
                    # Cursor entries
                    content = entry.get("content", {})
                    if content.get("entryType") == "TimelineTimelineCursor":
                        if content.get("cursorType") == "Bottom":
                            next_cursor = content.get("value")
                        continue

                    # Tweet entries
                    tweet = self._extract_tweet(entry)
                    if tweet:
                        tweets.append(tweet)

            elif instruction.get("type") == "TimelineReplaceEntry":
                entry = instruction.get("entry", {})
                content = entry.get("content", {})
                if content.get("cursorType") == "Bottom":
                    next_cursor = content.get("value")

        return tweets, next_cursor

    def _extract_tweet(self, entry: dict) -> dict | None:
        """Pull out a normalized tweet dict from a timeline entry."""
        try:
            item_content = (
                entry.get("content", {})
                     .get("itemContent", {})
            )
            tweet_result = item_content.get("tweet_results", {}).get("result", {})

            # Handle tweet tombstones (deleted/unavailable)
            if tweet_result.get("__typename") == "TweetTombstone":
                return None

            # Handle retweets — go to the core tweet
            if tweet_result.get("__typename") == "TweetWithVisibilityResults":
                tweet_result = tweet_result.get("tweet", tweet_result)

            legacy = tweet_result.get("legacy", {})
            if not legacy:
                return None

            return {
                "id":         legacy.get("id_str"),
                "text":       legacy.get("full_text", ""),
                "created_at": legacy.get("created_at"),
                "likes":      legacy.get("favorite_count", 0),
                "retweets":   legacy.get("retweet_count", 0),
                "is_reply":   bool(legacy.get("in_reply_to_status_id_str")),
                "is_retweet": legacy.get("full_text", "").startswith("RT @"),
            }
        except Exception:
            return None

    # ── Tweet Deletion ───────────────────────────────────────────────────────

    def delete_tweet(self, tweet_id: str) -> bool:
        """Delete a tweet by ID. Returns True on success."""
        qid = QUERY_IDS["DeleteTweet"]
        url = f"{API_URL}/{qid}/DeleteTweet"
        payload = {
            "variables": {"tweet_id": tweet_id, "dark_request": False},
            "queryId":   qid,
        }
        try:
            resp = self._post(url, json=payload)
            return resp.status_code == 200
        except Exception as e:
            log.error(f"Failed to delete tweet {tweet_id}: {e}")
            return False

    # ── Bookmark Fetching & Deletion ─────────────────────────────────────────

    def fetch_bookmarks_page(self, cursor: str | None = None) -> tuple[list[dict], str | None]:
        """Fetch one page of bookmarks. Returns (bookmarks, next_cursor)."""
        qid = QUERY_IDS["Bookmarks"]
        url = f"{API_URL}/{qid}/Bookmarks"

        import json
        variables = {"count": 100, "includePromotedContent": False}
        if cursor:
            variables["cursor"] = cursor

        params = {
            "variables": json.dumps(variables),
            "features":  json.dumps(TWEET_FEATURES),
        }

        resp = self._get(url, params=params)
        data = resp.json()
        return self._parse_bookmarks(data)

    def _parse_bookmarks(self, data: dict) -> tuple[list[dict], str | None]:
        """Extract bookmark tweet objects and pagination cursor."""
        tweets      = []
        next_cursor = None

        try:
            instructions = (
                data.get("data", {})
                    .get("bookmark_timeline_v2", {})
                    .get("timeline", {})
                    .get("instructions", [])
            )
        except AttributeError:
            return tweets, None

        for instruction in instructions:
            if instruction.get("type") == "TimelineAddEntries":
                for entry in instruction.get("entries", []):
                    content = entry.get("content", {})
                    if content.get("entryType") == "TimelineTimelineCursor":
                        if content.get("cursorType") == "Bottom":
                            next_cursor = content.get("value")
                        continue
                    tweet = self._extract_tweet(entry)
                    if tweet:
                        tweets.append(tweet)

        return tweets, next_cursor

    def delete_bookmark(self, tweet_id: str) -> bool:
        """Remove a single bookmark by tweet ID."""
        qid = QUERY_IDS["DeleteBookmark"]
        url = f"{API_URL}/{qid}/DeleteBookmark"
        payload = {
            "variables": {"tweet_id": tweet_id},
            "queryId":   qid,
        }
        try:
            resp = self._post(url, json=payload)
            return resp.status_code == 200
        except Exception as e:
            log.error(f"Failed to delete bookmark {tweet_id}: {e}")
            return False

    def delete_all_bookmarks(self) -> bool:
        """Use X's native 'clear all bookmarks' endpoint if available."""
        qid = QUERY_IDS["BookmarksAllDelete"]
        url = f"{API_URL}/{qid}/BookmarksAllDelete"
        payload = {"variables": {}, "queryId": qid}
        try:
            resp = self._post(url, json=payload)
            return resp.status_code == 200
        except Exception as e:
            log.warning(f"Bulk bookmark delete failed ({e}), will delete individually.")
            return False

    # ── HTTP Helpers with Rate-Limit Backoff ─────────────────────────────────

    def _get(self, url: str, **kwargs) -> requests.Response:
        return self._request("GET", url, **kwargs)

    def _post(self, url: str, **kwargs) -> requests.Response:
        return self._request("POST", url, **kwargs)

    def _request(self, method: str, url: str, retries: int = 5, **kwargs) -> requests.Response:
        for attempt in range(retries):
            try:
                resp = self.session.request(method, url, timeout=30, **kwargs)

                if resp.status_code == 429:
                    wait = self._parse_rate_limit_reset(resp)
                    log.warning(f"Rate limited. Waiting {wait}s before retry...")
                    time.sleep(wait)
                    continue

                if resp.status_code in (401, 403):
                    raise PermissionError(
                        f"HTTP {resp.status_code}: Authentication error. "
                        "Your auth_token or ct0 may have expired."
                    )

                resp.raise_for_status()
                return resp

            except (requests.ConnectionError, requests.Timeout) as e:
                wait = (2 ** attempt) + random.uniform(0, 1)
                log.warning(f"Network error: {e}. Retrying in {wait:.1f}s...")
                time.sleep(wait)

        raise RuntimeError(f"Request to {url} failed after {retries} attempts.")

    @staticmethod
    def _parse_rate_limit_reset(resp: requests.Response) -> int:
        """Parse X-RateLimit-Reset header and return seconds to wait."""
        reset_ts = resp.headers.get("x-rate-limit-reset")
        if reset_ts:
            wait = max(0, int(reset_ts) - int(time.time())) + 5
            return min(wait, 900)  # Cap at 15 minutes
        return 60  # Default fallback


def parse_tweet_date(created_at: str | None) -> datetime | None:
    """Parse Twitter's 'Wed May 20 14:02:00 +0000 2026' date format."""
    if not created_at:
        return None
    try:
        return datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
    except ValueError:
        return None
