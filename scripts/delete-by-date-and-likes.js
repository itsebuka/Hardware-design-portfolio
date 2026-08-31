/**
 * =====================================================
 *  X-Purger | Delete Tweets & Replies by Date Range + Min Likes
 *  Target URL: https://x.com/YOUR_USERNAME/with_replies
 * =====================================================
 *
 * HOW TO USE:
 *  1. Go to: https://x.com/YOUR_USERNAME/with_replies
 *  2. Open DevTools: F12 → Console tab
 *  3. Paste this entire script and press Enter
 *
 * WHAT IT DOES:
 *  - Targets ALL posts (original tweets + replies) in your timeline
 *  - Deletes posts that were created between START_DATE and END_DATE
 *  - ONLY deletes posts with fewer than MIN_LIKES likes
 *  - Skips (preserves) posts at or above MIN_LIKES
 *
 * CONFIG (edit these before pasting):
 * =====================================================
 */
const CONFIG = {
  START_DATE: new Date("2025-11-01T00:00:00Z"),   // Nov 2025
  END_DATE:   new Date("2026-06-30T23:59:59Z"),   // End of June 2026
  MIN_LIKES:  2,                                   // Delete if likes < 2 (i.e. 0 or 1)
  SCROLL_DELAY_MS: 2500,
  ACTION_DELAY_MS: 700,
  MAX_SCROLL_RETRIES: 6,
};

(() => {
  let deletedCount  = 0;
  let skippedCount  = 0;
  let outOfRangeCount = 0;
  let scrollRetries = 0;

  const delay = (ms) => new Promise((r) => setTimeout(r, ms));
  const jitter = (base) => base + Math.random() * 400;

  function log(msg, color = "#1d9bf0") {
    console.log(`%c[X-Purger] ${msg}`, `color:${color};font-weight:bold;font-size:13px;`);
  }

  function printStatus() {
    log(
      `🗑️ Deleted: ${deletedCount} | ✅ Kept (liked): ${skippedCount} | ⏭️ Out of range: ${outOfRangeCount}`,
      "#f91880"
    );
  }

  /**
   * Extract the post date from a tweet article element.
   * Looks for the <time> element inside the article.
   */
  function getPostDate(article) {
    const timeEl = article.querySelector("time");
    if (!timeEl) return null;
    const dt = timeEl.getAttribute("datetime");
    return dt ? new Date(dt) : null;
  }

  /**
   * Extract like count from a tweet article element.
   * Looks for the like button's aria-label which contains the count.
   */
  function getLikeCount(article) {
    // Try the like button aria-label first: "28 Likes" / "Like" (0)
    const likeBtn = article.querySelector('[data-testid="like"], [data-testid="unlike"]');
    if (!likeBtn) return 0;

    const ariaLabel = likeBtn.getAttribute("aria-label") || "";
    const match = ariaLabel.match(/(\d[\d,]*)\s*like/i);
    if (match) return parseInt(match[1].replace(/,/g, ""), 10);

    // Fallback: look for the count span next to the like button
    const countSpan = likeBtn.closest('[role="group"]')
      ?.querySelector('[data-testid="like"] + * span, [data-testid="unlike"] + * span');
    if (countSpan) {
      const n = parseInt(countSpan.textContent.trim().replace(/,/g, ""), 10);
      return isNaN(n) ? 0 : n;
    }

    return 0;
  }

  async function openMoreMenu(article) {
    const caret = article.querySelector('button[data-testid="caret"]');
    if (!caret) return false;
    caret.scrollIntoView({ behavior: "smooth", block: "center" });
    await delay(300);
    caret.click();
    await delay(600);
    return true;
  }

  async function clickDeleteInMenu() {
    const items = Array.from(document.querySelectorAll('[role="menuitem"]'));
    const del = items.find((el) => el.textContent.trim().toLowerCase().includes("delete"));
    if (!del) {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await delay(300);
      return false;
    }
    del.click();
    await delay(700);
    return true;
  }

  async function confirmDelete() {
    const btn = document.querySelector('[data-testid="confirmationSheetConfirm"]');
    if (!btn) return false;
    btn.click();
    await delay(900);
    return true;
  }

  async function processArticles() {
    const articles = Array.from(document.querySelectorAll('article[data-testid="tweet"]'));

    if (articles.length === 0) {
      if (scrollRetries >= CONFIG.MAX_SCROLL_RETRIES) {
        log(
          `✅ Finished! Deleted: ${deletedCount} | Kept (liked): ${skippedCount} | Out of range: ${outOfRangeCount}`,
          "#00ba7c"
        );
        return;
      }
      log("No articles visible. Scrolling to load more...", "#ffd400");
      window.scrollBy(0, 2500);
      scrollRetries++;
      await delay(jitter(CONFIG.SCROLL_DELAY_MS));
      return processArticles();
    }

    scrollRetries = 0;

    for (const article of articles) {
      try {
        const postDate  = getPostDate(article);
        const likeCount = getLikeCount(article);

        // ── Date range check ──
        if (!postDate || postDate < CONFIG.START_DATE || postDate > CONFIG.END_DATE) {
          outOfRangeCount++;
          continue;
        }

        // ── Likes check — KEEP posts with MIN_LIKES or more ──
        if (likeCount >= CONFIG.MIN_LIKES) {
          skippedCount++;
          log(
            `💛 Keeping post (${likeCount} likes) — ${postDate.toLocaleDateString()}`,
            "#ffd400"
          );
          continue;
        }

        // ── This post qualifies for deletion ──
        const opened = await openMoreMenu(article);
        if (!opened) { outOfRangeCount++; continue; }

        const found = await clickDeleteInMenu();
        if (!found) { outOfRangeCount++; continue; }

        const confirmed = await confirmDelete();
        if (confirmed) {
          deletedCount++;
          printStatus();
          // Rate-limit protection every 60 deletes
          if (deletedCount % 60 === 0) {
            log("🛑 Pausing 45s to avoid rate limits...", "#ffd400");
            await delay(45_000);
          }
        } else {
          document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
          await delay(300);
        }

        await delay(jitter(CONFIG.ACTION_DELAY_MS));
      } catch (err) {
        console.error("[X-Purger] Error:", err);
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
        await delay(500);
      }
    }

    window.scrollBy(0, 2500);
    await delay(jitter(CONFIG.SCROLL_DELAY_MS));
    processArticles();
  }

  log(`🚀 Starting targeted purge on ${window.location.href}`, "#1d9bf0");
  log(
    `📅 Range: ${CONFIG.START_DATE.toDateString()} → ${CONFIG.END_DATE.toDateString()} | Min likes to keep: ${CONFIG.MIN_LIKES}`,
    "#1d9bf0"
  );
  log("Press F5 at any time to stop.", "#ffd400");
  processArticles();
})();
