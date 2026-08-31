/**
 * =====================================================
 *  X-Purger | Automated Bookmark Clearer
 *  Target URL: https://x.com/i/bookmarks
 * =====================================================
 *
 * HOW TO USE:
 *  1. Go to: https://x.com/i/bookmarks
 *  2. Open DevTools: F12 → Console tab
 *  3. Paste this entire script and press Enter
 *
 * WHAT IT DOES:
 *  - Automatically removes every saved bookmark from your account
 *  - Auto-scrolls to load more bookmarks as it clears them
 *  - Shows a live counter of removed bookmarks
 *  - Handles the confirmation dialog if X shows one
 *
 * NOTE: This removes bookmarks from YOUR view only.
 *       The original tweets still exist on other accounts.
 * =====================================================
 */
(() => {
  let removedCount  = 0;
  let scrollRetries = 0;
  const MAX_RETRIES = 6;

  const delay = (ms) => new Promise((r) => setTimeout(r, ms));
  const jitter = (base) => base + Math.random() * 300;

  function log(msg, color = "#1d9bf0") {
    console.log(`%c[X-Purger Bookmarks] ${msg}`, `color:${color};font-weight:bold;font-size:13px;`);
  }

  /**
   * Find the "More" (···) button on a tweet article and click it,
   * then select "Remove bookmark" from the dropdown.
   */
  async function removeBookmark(article) {
    // Step 1: Click the bookmark icon which on the bookmarks page acts as a toggle (unbookmark)
    // X renders an active bookmark button with data-testid="removeBookmark" or as part of the share menu
    // Try direct unbookmark button first
    const directUnbookmark = article.querySelector('[data-testid="removeBookmark"]');
    if (directUnbookmark) {
      directUnbookmark.scrollIntoView({ behavior: "smooth", block: "center" });
      await delay(250);
      directUnbookmark.click();
      await delay(600);
      return true;
    }

    // Fallback: open the share / more menu and look for "Remove bookmark"
    const shareBtn = article.querySelector('[data-testid="bookmark"]');
    if (shareBtn) {
      shareBtn.scrollIntoView({ behavior: "smooth", block: "center" });
      await delay(250);
      shareBtn.click();
      await delay(600);

      const menuItems = Array.from(document.querySelectorAll('[role="menuitem"]'));
      const removeItem = menuItems.find((el) => {
        const t = el.textContent.trim().toLowerCase();
        return t.includes("remove bookmark") || t.includes("unbookmark");
      });

      if (removeItem) {
        removeItem.click();
        await delay(700);
        return true;
      }

      // Close menu if not found
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await delay(300);
    }

    // Last resort: use the caret (···) menu
    const caret = article.querySelector('button[data-testid="caret"]');
    if (caret) {
      caret.scrollIntoView({ behavior: "smooth", block: "center" });
      await delay(300);
      caret.click();
      await delay(600);

      const menuItems = Array.from(document.querySelectorAll('[role="menuitem"]'));
      const removeItem = menuItems.find((el) => {
        const t = el.textContent.trim().toLowerCase();
        return t.includes("remove bookmark") || t.includes("unbookmark");
      });

      if (removeItem) {
        removeItem.click();
        await delay(700);
        return true;
      }

      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await delay(300);
    }

    return false;
  }

  async function clearBookmarks() {
    const articles = Array.from(document.querySelectorAll('article[data-testid="tweet"]'));

    if (articles.length === 0) {
      if (scrollRetries >= MAX_RETRIES) {
        log(`✅ All bookmarks cleared! Total removed: ${removedCount}`, "#00ba7c");
        return;
      }
      log("No bookmarks visible. Scrolling to load more...", "#ffd400");
      window.scrollBy(0, 2500);
      scrollRetries++;
      await delay(jitter(3000));
      return clearBookmarks();
    }

    scrollRetries = 0;

    for (const article of articles) {
      try {
        const success = await removeBookmark(article);
        if (success) {
          removedCount++;
          log(`🔖 Removed bookmark #${removedCount}`, "#1d9bf0");
        }
        await delay(jitter(600));
      } catch (err) {
        console.error("[X-Purger Bookmarks] Error:", err);
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
        await delay(400);
      }
    }

    // Also check for X's native "Clear all bookmarks" button at the top
    const clearAllBtn = Array.from(document.querySelectorAll('[role="menuitem"], button')).find(
      (el) => el.textContent.trim().toLowerCase().includes("clear all bookmarks")
    );
    if (clearAllBtn) {
      log("Found 'Clear all bookmarks' button — clicking it!", "#00ba7c");
      clearAllBtn.click();
      await delay(800);
      // Confirm if there's a dialog
      const confirmBtn = document.querySelector('[data-testid="confirmationSheetConfirm"]');
      if (confirmBtn) {
        confirmBtn.click();
        log("✅ Confirmed clear all!", "#00ba7c");
        return;
      }
    }

    window.scrollBy(0, 2500);
    await delay(jitter(2500));
    clearBookmarks();
  }

  log(`🚀 Starting Bookmark Purge on: ${window.location.href}`, "#1d9bf0");
  log("Press F5 at any time to stop.", "#ffd400");

  // First try X's native "Clear all bookmarks" via the top-right "···" menu on the bookmarks page
  const moreOptionsBtn = document.querySelector('[aria-label="More options"]');
  if (moreOptionsBtn) {
    moreOptionsBtn.click();
    setTimeout(async () => {
      await delay(500);
      const items = Array.from(document.querySelectorAll('[role="menuitem"]'));
      const clearAll = items.find((el) => el.textContent.toLowerCase().includes("clear all"));
      if (clearAll) {
        clearAll.click();
        await delay(800);
        const confirmBtn = document.querySelector('[data-testid="confirmationSheetConfirm"]');
        if (confirmBtn) {
          confirmBtn.click();
          log("✅ Cleared all bookmarks via native menu!", "#00ba7c");
          return;
        }
      }
      // Fallback to individual removal
      clearBookmarks();
    }, 600);
  } else {
    clearBookmarks();
  }
})();
