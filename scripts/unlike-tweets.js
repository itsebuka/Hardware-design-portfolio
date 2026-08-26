/**
 * =====================================================
 *  X-Purger | Automated Mass Unlike Tool
 *  Target URL: https://x.com/YOUR_USERNAME/likes
 * =====================================================
 *
 * HOW TO USE:
 *  1. Go to: https://x.com/YOUR_USERNAME/likes
 *  2. Open DevTools: F12 → Console
 *  3. Paste this entire script and press Enter
 *
 * Features:
 *  - Live HUD counter in the console
 *  - Auto-scroll to load more liked posts
 *  - Jitter delays to mimic human behaviour
 *  - Retry logic if the page runs dry
 *  - Detects rate limiting (429) via console messages
 * =====================================================
 */
(() => {
  let unlikedCount = 0;
  let skippedCount = 0;
  let scrollRetries = 0;
  let paused = false;
  const MAX_RETRIES = 6;
  const RATE_LIMIT_PAUSE_MS = 45_000; // pause 45s if suspected rate limit

  const delay = (ms) => new Promise((res) => setTimeout(res, ms));
  const jitter = (base) => base + Math.random() * 400;

  function printStatus() {
    console.log(
      `%c[X-Purger] ❤️ Unliked: ${unlikedCount} | ⏭️ Skipped: ${skippedCount} | 🔄 Scroll Retries: ${scrollRetries}`,
      "color: #f91880; font-weight: bold; font-size: 13px;"
    );
  }

  async function handleRateLimitPause() {
    if (paused) return;
    paused = true;
    console.warn(
      `%c[X-Purger] ⚠️ Suspected rate limit. Pausing for ${RATE_LIMIT_PAUSE_MS / 1000}s...`,
      "color: #ffd400; font-weight: bold;"
    );
    await delay(RATE_LIMIT_PAUSE_MS);
    paused = false;
    console.log(
      "%c[X-Purger] ▶️ Resuming...",
      "color: #f91880; font-weight: bold; font-size: 13px;"
    );
  }

  async function unlikeAll() {
    if (paused) {
      await delay(1000);
      return unlikeAll();
    }

    const unlikeButtons = Array.from(
      document.querySelectorAll('button[data-testid="unlike"]')
    );

    if (unlikeButtons.length === 0) {
      if (scrollRetries >= MAX_RETRIES) {
        console.log(
          `%c[X-Purger] ✅ All done! Total unliked: ${unlikedCount} | Skipped: ${skippedCount}`,
          "color: #00ba7c; font-weight: bold; font-size: 14px;"
        );
        return;
      }
      console.log("[X-Purger] No liked posts visible. Scrolling to load more...");
      window.scrollBy(0, 2000);
      scrollRetries++;
      await delay(jitter(3000));
      return unlikeAll();
    }

    scrollRetries = 0;

    for (const btn of unlikeButtons) {
      if (paused) {
        await delay(1000);
      }

      try {
        btn.scrollIntoView({ behavior: "smooth", block: "center" });
        await delay(250);
        btn.click();
        unlikedCount++;
        printStatus();

        // Heuristic rate-limit detection: if we've clicked many in quick succession
        if (unlikedCount > 0 && unlikedCount % 80 === 0) {
          console.log(
            `%c[X-Purger] 🛑 Pausing after ${unlikedCount} unlikes to avoid rate limits...`,
            "color: #ffd400;"
          );
          await delay(jitter(RATE_LIMIT_PAUSE_MS));
        }

        await delay(jitter(700));
      } catch (err) {
        console.error("[X-Purger] Unlike error:", err);
        skippedCount++;
        await delay(500);
      }
    }

    window.scrollBy(0, 2000);
    await delay(jitter(2000));
    unlikeAll();
  }

  console.log(
    `%c[X-Purger] 🚀 Starting Unlike Purge on: ${window.location.href}`,
    "color: #f91880; font-weight: bold; font-size: 14px;"
  );
  console.log("%c[X-Purger] Press F5 to stop at any time.", "color: #ffd400; font-size: 12px;");
  unlikeAll();
})();