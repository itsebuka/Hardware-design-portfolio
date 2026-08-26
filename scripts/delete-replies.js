/**
 * =====================================================
 *  X-Purger | Automated Mass Reply Deleter
 *  Target URL: https://x.com/YOUR_USERNAME/with_replies
 * =====================================================
 *
 * HOW TO USE:
 *  1. Go to: https://x.com/YOUR_USERNAME/with_replies
 *  2. Open DevTools: F12 → Console
 *  3. Paste this entire script and press Enter
 *
 * NOTE: This script only deletes YOUR replies (posts where
 * you replied to someone). It skips original tweets on the feed.
 * =====================================================
 */
(() => {
  let deletedCount = 0;
  let skippedCount = 0;
  let retries = 0;
  const MAX_RETRIES = 5;

  const delay = (ms) => new Promise((res) => setTimeout(res, ms));
  const jitter = (base) => base + Math.random() * 400;

  function printStatus() {
    console.log(
      `%c[X-Purger] 🗑️  Deleted: ${deletedCount} | ⏭️ Skipped: ${skippedCount} | 🔄 Retries: ${retries}`,
      "color: #1d9bf0; font-weight: bold; font-size: 13px;"
    );
  }

  async function openDeleteMenu(article) {
    // Find the "More" (···) button within the tweet article
    const moreBtn = article.querySelector('button[data-testid="caret"]');
    if (!moreBtn) return false;

    moreBtn.scrollIntoView({ behavior: "smooth", block: "center" });
    await delay(300);
    moreBtn.click();
    await delay(600);
    return true;
  }

  async function clickDeleteOption() {
    // Find "Delete" in the dropdown menu
    const menuItems = Array.from(document.querySelectorAll('[role="menuitem"]'));
    const deleteItem = menuItems.find((el) =>
      el.textContent.trim().toLowerCase().includes("delete")
    );
    if (!deleteItem) {
      // Close any open dropdown and skip
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await delay(300);
      return false;
    }
    deleteItem.click();
    await delay(700);
    return true;
  }

  async function confirmDeletion() {
    // Confirm the "Delete" button in the confirmation dialog
    const confirmBtn = document.querySelector('[data-testid="confirmationSheetConfirm"]');
    if (!confirmBtn) return false;
    confirmBtn.click();
    await delay(800);
    return true;
  }

  async function deleteReplies() {
    // Get all tweet articles currently in view
    const articles = Array.from(document.querySelectorAll('article[data-testid="tweet"]'));

    if (articles.length === 0) {
      if (retries >= MAX_RETRIES) {
        console.log(
          `%c[X-Purger] ✅ Done! Total deleted: ${deletedCount} | Skipped: ${skippedCount}`,
          "color: #00ba7c; font-weight: bold; font-size: 14px;"
        );
        return;
      }
      // Scroll down to load more
      console.log("[X-Purger] No more articles found. Scrolling to load more...");
      window.scrollBy(0, 2000);
      retries++;
      await delay(3000);
      return deleteReplies();
    }

    retries = 0; // reset retry counter since we found articles

    for (const article of articles) {
      try {
        // Only attempt to delete if this article contains a "caret" (options) button
        const caretBtn = article.querySelector('button[data-testid="caret"]');
        if (!caretBtn) {
          skippedCount++;
          continue;
        }

        const opened = await openDeleteMenu(article);
        if (!opened) {
          skippedCount++;
          continue;
        }

        const deleteFound = await clickDeleteOption();
        if (!deleteFound) {
          skippedCount++;
          continue;
        }

        const confirmed = await confirmDeletion();
        if (confirmed) {
          deletedCount++;
          printStatus();
        } else {
          skippedCount++;
          // Close any stray modal
          document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
          await delay(300);
        }

        await delay(jitter(800));
      } catch (err) {
        console.error("[X-Purger] Error during deletion:", err);
        // Close any open menus/modals before continuing
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
        await delay(500);
      }
    }

    // Scroll down and process the next batch
    window.scrollBy(0, 2000);
    await delay(jitter(2000));
    deleteReplies();
  }

  console.log(
    `%c[X-Purger] 🚀 Starting Reply Purge on: ${window.location.href}`,
    "color: #1d9bf0; font-weight: bold; font-size: 14px;"
  );
  console.log("%c[X-Purger] Press F5 to stop at any time.", "color: #ffd400; font-size: 12px;");
  deleteReplies();
})();
