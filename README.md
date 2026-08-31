# 🐦 X-Purger Tool

> **Purge your Twitter/X history — delete tweets, replies, reposts, and unlike posts — in bulk.**
> Works via Browser Console (no setup), GitHub Codespaces (1-click), or GitHub Actions (automated).

---

## ✨ What This Does

| Script | What It Deletes | How to Use |
|--------|----------------|------------|
| `delete-tweets.js` | Your original tweets | Browser Console |
| `delete-replies.js` | Your replies to others | Browser Console |
| `delete-reposts.js` | Your retweets/reposts | Browser Console |
| `unlike-tweets.js` | Posts you have liked | Browser Console |
| `delete-by-date-and-likes.js` | Tweets & replies in a date range with < N likes | Browser Console |
| `clear-bookmarks.js` | All your saved bookmarks | Browser Console |
| `python-archive-parser.py` | Extracts IDs from your archive | Terminal / Codespaces / Actions |

---

## 🚀 Option 1: Browser Console (Zero Setup — Works Right Now)

**No coding skills needed.** Just open Twitter in your browser.

### Step-by-Step

1. **Log in** to [x.com](https://x.com)
2. Navigate to the correct page:

   | Goal | Go to |
   |------|-------|
   | Delete by date range + likes filter | `https://x.com/YOUR_USERNAME/with_replies` |
   | Clear all bookmarks | `https://x.com/i/bookmarks` |
   | Delete tweets | `https://x.com/YOUR_USERNAME` |
   | Delete replies | `https://x.com/YOUR_USERNAME/with_replies` |
   | Undo reposts | `https://x.com/YOUR_USERNAME` |
   | Unlike posts | `https://x.com/YOUR_USERNAME/likes` |

3. Press **F12** (Windows) or **Cmd+Option+J** (Mac) to open DevTools
4. Click the **Console** tab
5. **Copy the script** you want from the `scripts/` folder
6. **Paste it** into the console and press **Enter**
7. Watch the live counter in the console — press **F5** at any time to stop

> ⚠️ Twitter may show a warning about pasting code. Type `allow pasting` and press Enter if prompted.

---

## ☁️ Option 2: GitHub Codespaces (1-Click Cloud Environment)

Run the archive parser in a fully configured cloud environment — **no local Python install needed**.

### Step-by-Step

1. **Fork this repository** to your own GitHub account
2. Click the green **Code** button → **Codespaces** tab → **Create codespace on main**
3. Wait ~60 seconds for the environment to set up automatically
4. Upload your Twitter archive (`tweet.js` or `archive.zip`) to the workspace
5. Run the parser in the terminal:

```bash
# Basic — extract all tweet IDs
python scripts/python-archive-parser.py --archive tweet.js --stats

# Filter by date range
python scripts/python-archive-parser.py --archive tweet.js \
  --start-date 2023-01-01 --end-date 2023-12-31 --stats

# Only extract replies (not original tweets)
python scripts/python-archive-parser.py --archive tweet.js --type replies --stats

# Protect your popular posts (skip tweets with 50+ likes)
python scripts/python-archive-parser.py --archive tweet.js --min-likes 50 --stats

# Full example
python scripts/python-archive-parser.py \
  --archive tweet.js \
  --start-date 2022-01-01 \
  --end-date 2024-12-31 \
  --type all \
  --min-likes 100 \
  --keyword "old take" \
  --output my_ids.txt \
  --stats
```

---

## ⚙️ Option 3: GitHub Actions (Automated, Scheduled, No Computer Needed)

Run the archive parser automatically in the cloud via GitHub Actions.

### Step-by-Step

1. **Fork this repository** (must be **private** to protect your data)
2. Go to your fork → **Actions** tab → Enable workflows if prompted
3. Click **🐦 X-Purger — Archive ID Extractor** → **Run workflow**
4. Fill in the inputs:
   - **Start date** / **End date** — e.g. `2022-01-01`
   - **Type** — `tweets`, `replies`, `reposts`, `likes`, or `all`
   - **Min likes** — set to e.g. `100` to protect popular posts
   - **Dry run** — keep `true` to just preview what would be deleted
5. Click **Run workflow** and wait for it to finish
6. Download the **`filtered-tweet-ids`** artifact to see the extracted IDs

> 🔒 Your `tweet.js` archive file should **never** be committed to GitHub.
> Upload it via the "twitter-archive" artifact upload step or keep it local.

---

## 📦 How to Download Your Twitter Archive

1. Go to **Settings** → **Your Account** → **Download an archive of your data**
2. Twitter will email you a download link (may take a few minutes to 24 hours)
3. Download and unzip — look for the **`data/tweet.js`** file inside

---

## 🛡️ Safety & Rate Limits

| Rule | Details |
|------|---------|
| **Jitter delays** | All scripts use randomized delays to mimic human behaviour |
| **Auto-pause** | Unlike script pauses every 80 unlikes for 45 seconds |
| **Dry run** | Archive parser supports `--stats` to preview without deleting |
| **Private fork** | Always use a private fork if uploading archives or secrets |
| **Checkpoint** | Archive parser never re-processes the same IDs (planned) |

> ⚠️ **Never share** your `auth_token` or `ct0` cookies. They give full access to your account.

---

## 📁 Project Structure

```
X-purger-tool/
├── .devcontainer/
│   └── devcontainer.json        # GitHub Codespaces auto-setup
├── .github/
│   └── workflows/
│       └── purge.yml            # GitHub Actions workflow
├── scripts/
│   ├── delete-tweets.js         # Browser: delete original tweets
│   ├── delete-replies.js        # Browser: delete your replies
│   ├── delete-reposts.js        # Browser: undo reposts
│   ├── unlike-tweets.js         # Browser: unlike all liked posts
│   └── python-archive-parser.py # CLI: parse archive & extract IDs
├── .env.example                 # Credentials template (never commit .env)
├── .gitignore                   # Protects secrets & archive files
├── requirements.txt             # Python dependencies
└── README.md
```

---

## ❓ FAQ

**Q: Will this get my account banned?**
> The browser scripts use human-like delays and jitter to avoid detection. Don't run them for more than a few hours at a time. Take breaks.

**Q: Why can't I see old tweets in the browser scripts?**
> Twitter only loads ~3,200 recent tweets in the timeline. For older posts, use the **Python archive parser** with your downloaded archive to get the IDs.

**Q: The script stopped — what do I do?**
> Just re-run it. The browser scripts continue from where they can see on screen. For large archives, re-paste and it will continue.

**Q: Does this work on private/protected accounts?**
> Yes — as long as you are logged in as the account owner.

---

## 📄 License

MIT — Use freely, modify, share. Not affiliated with X Corp / Twitter.
