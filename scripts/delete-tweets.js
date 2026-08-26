/**
 * =====================================================
 *  X-Purger | Automated Mass Tweet Deleter
 *  Target URL: https://x.com/YOUR_USERNAME
 * =====================================================
 *
 * HOW TO USE:
 *  1. Go to your Profile: https://x.com/YOUR_USERNAME
 *  2. Open DevTools: F12 → Console
 *  3. Paste this entire script and press Enter
 *
 * Features:
 *  - Deletes original tweets (skips reposts by default)
 *  - Live console HUD counter
 *  - Auto-scroll, retry, and jitter delays
 *  - Rate-limit protection with auto-pause
 * =====================================================
 */
(() => {
  let deletedCount = 0;
  let skippedCount = 0;
  let scrollRetries = 0;
  const MAX_RETRIES = 5;
  const RATE_LIMIT_PAUSE_MS = 45_000;

  const delay = (ms) => new Promise((res) => setTimeout(res, ms));
  const jitter = (base) => base + Math.random() * 400;

  function printStatus() {
    console.log(
      `%c[X-Purger] 🗑️  Deleted: ${deletedCount} | ⏭️ Skipped: ${skippedCount}`,
      "color: #1d9bf0; font-weight: bold; font-size: 13px;"
    );
  }

  async function openDeleteMenu(article) {
    const moreBtn = article.querySelector('button[data-testid="caret"]');
    if (!moreBtn) return false;
    moreBtn.scrollIntoView({ behavior: "smooth", block: "center" });
    await delay(300);
    moreBtn.click();
    await delay(600);
    return true;
  }

  async function clickDeleteInMenu() {
    const menuItems = Array.from(document.querySelectorAll('[role="menuitem"]'));
    const deleteItem = menuItems.find((el) =>
      el.textContent.trim().toLowerCase().includes("delete")
    );
    if (!deleteItem) {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await delay(300);
      return false;
    }
    deleteItem.click();
    await delay(700);
    return true;
  }

  async function confirmDelete() {
    const confirmBtn = document.querySelector('[data-testid="confirmationSheetConfirm"]');
    if (!confirmBtn) return false;
    confirmBtn.click();
    await delay(800);
    return true;
  }

  async function deleteTweets() {
    const articles = Array.from(document.querySelectorAll('article[data-testid="tweet"]'));

    if (articles.length === 0) {
      if (scrollRetries >= MAX_RETRIES) {
        console.log(
          `%c[X-Purger] ✅ Done! Total deleted: ${deletedCount} | Skipped: ${skippedCount}`,
          "color: #00ba7c; font-weight: bold; font-size: 14px;"
        );
        return;
      }
      console.log("[X-Purger] No articles found. Scrolling to load more...");
      window.scrollBy(0, 2000);
      scrollRetries++;
      await delay(3000);
      return deleteTweets();
    }

    scrollRetries = 0;

    for (const article of articles) {
      try {
        const opened = await openDeleteMenu(article);
        if (!opened) {
          skippedCount++;
          continue;
        }

        const deleteFound = await clickDeleteInMenu();
        if (!deleteFound) {
          skippedCount++;
          continue;
        }

        const confirmed = await confirmDelete();
        if (confirmed) {
          deletedCount++;
          printStatus();

          // Rate-limit protection: pause every 60 deletions
          if (deletedCount > 0 && deletedCount % 60 === 0) {
            console.warn(
              `%c[X-Purger] 🛑 Pausing for ${RATE_LIMIT_PAUSE_MS / 1000}s to avoid rate limits...`,
              "color: #ffd400;"
            );
            await delay(RATE_LIMIT_PAUSE_MS);
          }
        } else {
          skippedCount++;
          document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
          await delay(300);
        }

        await delay(jitter(900));
      } catch (err) {
        console.error("[X-Purger] Error during deletion:", err);
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
        await delay(500);
      }
    }

    window.scrollBy(0, 2000);
    await delay(jitter(2500));
    deleteTweets();
  }

  console.log(
    `%c[X-Purger] 🚀 Starting Tweet Purge on: ${window.location.href}`,
    "color: #1d9bf0; font-weight: bold; font-size: 14px;"
  );
  console.log("%c[X-Purger] Press F5 to stop at any time.", "color: #ffd400; font-size: 12px;");
  deleteTweets();
})();
