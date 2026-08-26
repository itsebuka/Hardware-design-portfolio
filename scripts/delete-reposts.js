/**
 * =====================================================
 *  X-Purger | Automated Mass Repost (Retweet) Undoer
 *  Target URL: https://x.com/YOUR_USERNAME
 *              (or https://x.com/YOUR_USERNAME/retweets - if available)
 * =====================================================
 *
 * HOW TO USE:
 *  1. Go to your Profile: https://x.com/YOUR_USERNAME
 *  2. Open DevTools: F12 → Console
 *  3. Paste this entire script and press Enter
 *
 * This script finds all "Reposted" label entries in your
 * timeline and clicks the confirmation to undo the repost.
 * =====================================================
 */
(() => {
  let undoneCount = 0;
  let skippedCount = 0;
  let scrollRetries = 0;
  const MAX_RETRIES = 5;

  const delay = (ms) => new Promise((res) => setTimeout(res, ms));
  const jitter = (base) => base + Math.random() * 400;

  function printStatus() {
    console.log(
      `%c[X-Purger] 🔁 Undone Reposts: ${undoneCount} | ⏭️ Skipped: ${skippedCount}`,
      "color: #ff6b35; font-weight: bold; font-size: 13px;"
    );
  }

  async function undoRepost(retweetBtn) {
    // The retweet button's aria-label should say "Undo repost" when already retweeted
    if (!retweetBtn) return false;

    retweetBtn.scrollIntoView({ behavior: "smooth", block: "center" });
    await delay(300);
    retweetBtn.click(); // Opens the "Undo repost / Quote" dropdown
    await delay(700);

    // Look for "Undo repost" option in the dropdown
    const menuItems = Array.from(document.querySelectorAll('[role="menuitem"]'));
    const undoItem = menuItems.find((el) => {
      const text = el.textContent.trim().toLowerCase();
      return text.includes("undo repost") || text.includes("unretweet");
    });

    if (!undoItem) {
      // Close dropdown and skip
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await delay(300);
      return false;
    }

    undoItem.click();
    await delay(800);
    return true;
  }

  async function processReposts() {
    // Look for all retweet buttons that are currently "active" (meaning you have retweeted)
    // Active retweet buttons have aria-label containing "Undo repost"
    const retweetButtons = Array.from(
      document.querySelectorAll('button[data-testid="unretweet"]')
    );

    if (retweetButtons.length === 0) {
      if (scrollRetries >= MAX_RETRIES) {
        console.log(
          `%c[X-Purger] ✅ Done! Total reposts undone: ${undoneCount} | Skipped: ${skippedCount}`,
          "color: #00ba7c; font-weight: bold; font-size: 14px;"
        );
        return;
      }
      console.log("[X-Purger] No repost buttons found. Scrolling to load more...");
      window.scrollBy(0, 2000);
      scrollRetries++;
      await delay(3000);
      return processReposts();
    }

    scrollRetries = 0;

    for (const btn of retweetButtons) {
      try {
        const success = await undoRepost(btn);
        if (success) {
          undoneCount++;
          printStatus();
        } else {
          skippedCount++;
        }
        await delay(jitter(900));
      } catch (err) {
        console.error("[X-Purger] Error undoing repost:", err);
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
        await delay(500);
      }
    }

    window.scrollBy(0, 2000);
    await delay(jitter(2500));
    processReposts();
  }

  console.log(
    `%c[X-Purger] 🚀 Starting Repost Purge on: ${window.location.href}`,
    "color: #ff6b35; font-weight: bold; font-size: 14px;"
  );
  console.log("%c[X-Purger] Press F5 to stop at any time.", "color: #ffd400; font-size: 12px;");
  processReposts();
})();
