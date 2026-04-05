---
name: bird-commands-reference
description: Fast X/Twitter CLI for reading tweets, bookmarks, search, and timeline operations using cookie authentication
---

# bird 🐦 — Fast X/Twitter CLI

A fast X/Twitter CLI for reading tweets, searching, managing bookmarks, and timeline operations via X/Twitter's GraphQL API (cookie auth).

## Description

bird v0.8.0 - Fast X/Twitter CLI by steipete (original repo deleted)

**Repository:** [LaceLetho/bird-cli-backup](https://github.com/LaceLetho/bird-cli-backup)
**Language:** TypeScript (99.8%), JavaScript (0.2%)
**Stars:** 0
**License:** MIT License

## ⚠️ Important Disclaimer

- Uses X/Twitter's **undocumented** web GraphQL API with cookie authentication
- **Strong recommendation: Use bird to READ tweets, not write**
- Avoid tweeting via CLI - you will hit blocks quickly. Bots are not welcome on X/Twitter
- For posting, use browser automation or pay for the official Twitter API
- Endpoints, query IDs, and anti-bot behavior can change without notice

## When to Use This Skill

Use this skill when you need to:
- **Read and fetch tweets** by ID or URL
- **Search tweets** with advanced queries (e.g., `from:username`)
- **Manage bookmarks** - list, filter, expand threads, unbookmark
- **Browse timelines** - home feed, user tweets, lists
- **Fetch news and trending** topics from X's Explore tabs
- **Get user information** - followers, following, account details
- **Navigate threads and replies** with context expansion
- **Work with bird as a TypeScript library**
- Understand authentication (cookies, environment variables, config)
- Look up command options, flags, and JSON output schemas

## 🚀 Quick Start

```bash
# Install
npm install -g @steipete/bird
# or via Homebrew (macOS)
brew install steipete/tap/bird

# Show logged-in account
bird whoami

# Check available credentials
bird check

# Read a tweet
bird read https://x.com/user/status/1234567890123456789
bird 1234567890123456789 --json

# Search tweets
bird search "from:username" -n 10

# Get user's recent tweets
bird user-tweets @username -n 20

# List bookmarks
bird bookmarks -n 10 --json
```

## 📚 Core Commands

### Reading Tweets

```bash
# Read single tweet (text or JSON)
bird read <tweet-id-or-url>
bird <tweet-id-or-url> --json

# Get full thread
bird thread <tweet-id-or-url> --json
bird thread <tweet-id-or-url> --max-pages 3

# Get replies to a tweet
bird replies <tweet-id-or-url> -n 50
bird replies <tweet-id-or-url> --all --json
```

### Search & Discovery

```bash
# Search tweets
bird search "from:username query" -n 20
bird search "keyword" --all --json

# Get mentions
bird mentions -n 10
bird mentions --user @username -n 5

# Browse home timeline
bird home -n 20
bird home --following --json

# User profile timeline
bird user-tweets @username -n 50 --json
```

### Bookmarks Management

```bash
# List bookmarks
bird bookmarks -n 10
bird bookmarks --all --json

# Bookmark folder
bird bookmarks --folder-id 123456789 -n 20

# Expand threads in bookmarks
bird bookmarks --include-parent --json
bird bookmarks --expand-root-only --json
bird bookmarks --author-chain --json

# Remove bookmarks
bird unbookmark 1234567890
bird unbookmark https://x.com/user/status/1234567890
```

**Bookmark Expansion Flags:**
- `--expand-root-only` - Expand threads only for root tweets
- `--author-chain` - Keep only bookmarked author's self-reply chain
- `--author-only` - Include all tweets from bookmarked author in thread
- `--full-chain-only` - Keep entire reply chain (all authors)
- `--include-ancestor-branches` - Include sibling branches with `--full-chain-only`
- `--include-parent` - Include direct parent tweet for non-root bookmarks
- `--thread-meta` - Add thread metadata to each tweet
- `--sort-chronological` - Sort globally oldest to newest

### News & Trending

```bash
# Get AI-curated news
bird news -n 10
bird news --ai-only -n 20

# Specific tabs
bird news --news-only --ai-only -n 10
bird news --sports -n 15
bird news --entertainment --ai-only -n 5

# Include related tweets
bird news --with-tweets --tweets-per-item 3 -n 10

# JSON output
bird news --json -n 5
bird news --json-full --ai-only -n 10
```

**News Tab Options:**
- `--for-you` - For You tab only
- `--news-only` - News tab only
- `--sports` - Sports tab only
- `--entertainment` - Entertainment tab only
- `--trending-only` - Trending tab only

### Lists

```bash
# Get your lists
bird lists --json
bird lists --member-of -n 20

# List timeline
bird list-timeline 1234567890 -n 20
bird list-timeline https://x.com/i/lists/1234567890 --all --json
```

### Social Graph

```bash
# Who you follow
bird following -n 20 --json
bird following --user 12345678 -n 10

# Your followers
bird followers -n 20 --json
bird followers --user 12345678 -n 10

# Get likes
bird likes -n 10 --all --json

# Account information
bird about @username --json
bird whoami
```

## 🔑 Authentication

Bird uses cookie-based authentication. Credentials are resolved in this order:

1. **CLI flags:** `--auth-token <token>` and `--ct0 <token>`
2. **Environment variables:** `AUTH_TOKEN`, `CT0` (fallback: `TWITTER_AUTH_TOKEN`, `TWITTER_CT0`)
3. **Browser cookies** (auto-extracted via `@steipete/sweet-cookie`)

### Browser Cookie Sources

```bash
# Set cookie source priority
bird --cookie-source safari search "query"
bird --cookie-source firefox --cookie-source chrome search "query"

# Chrome profiles
bird --chrome-profile "Profile 2" search "query"
bird --chrome-profile-dir "/path/to/Chromium/Profile" search "query"

# Firefox profiles
bird --firefox-profile "default-release" search "query"
```

**Cookie paths:**
- Safari: `~/Library/Cookies/Cookies.binarycookies`
- Chrome: `~/Library/Application Support/Google/Chrome/<Profile>/Cookies`
- Firefox: `~/Library/Application Support/Firefox/Profiles/<profile>/cookies.sqlite`

### Configuration File

Config precedence: CLI flags > env vars > project config > global config

**Global config:** `~/.config/bird/config.json5`
**Project config:** `./.birdrc.json5`

```json5
{
  // Cookie source order
  cookieSource: ["firefox", "safari"],
  chromeProfileDir: "/path/to/Chromium/Profile",
  firefoxProfile: "default-release",
  cookieTimeoutMs: 30000,
  timeoutMs: 20000,
  quoteDepth: 1
}
```

**Environment shortcuts:**
- `BIRD_TIMEOUT_MS`
- `BIRD_COOKIE_TIMEOUT_MS`
- `BIRD_QUOTE_DEPTH`

## 📊 JSON Output Schemas

### Tweet Object

```typescript
{
  id: string              // Tweet ID
  text: string            // Full text (includes Note/Article content)
  author: {
    username: string
    name: string
  }
  authorId?: string       // Author's user ID
  createdAt: string       // Timestamp
  replyCount: number
  retweetCount: number
  likeCount: number
  conversationId: string  // Thread conversation ID
  inReplyToStatusId?: string  // Parent tweet ID
  quotedTweet?: object    // Embedded quote (depth via --quote-depth)
}
```

### User Object

```typescript
{
  id: string
  username: string
  name: string
  description?: string
  followersCount?: number
  followingCount?: number
  isBlueVerified?: boolean
  profileImageUrl?: string
  createdAt?: string
}
```

### News Object

```typescript
{
  id: string              // Unique identifier
  headline: string        // News headline or trend title
  category?: string       // e.g., "AI · Technology", "Trending"
  timeAgo?: string        // Relative time (e.g., "2h ago")
  postCount?: number      // Number of posts
  description?: string
  url?: string
  tweets?: array          // Related tweets (with --with-tweets)
  _raw?: object           // Raw API response (with --json-full)
}
```

## 🔧 Global Options

```bash
--auth-token <token>      # Set auth_token cookie manually
--ct0 <token>             # Set ct0 cookie manually
--cookie-source <source>  # Browser source (safari|chrome|firefox)
--chrome-profile <name>   # Chrome profile name
--chrome-profile-dir <path>  # Chrome/Chromium profile directory
--firefox-profile <name>  # Firefox profile name
--cookie-timeout <ms>     # Cookie extraction timeout
--timeout <ms>            # Request timeout
--quote-depth <n>         # Max quoted tweet depth (default: 1)
--plain                   # Stable output (no emoji, no color)
--no-emoji                # Disable emoji
--no-color                # Disable ANSI colors (or NO_COLOR=1)
--json                    # JSON output
--json-full               # Full JSON with raw API response
```

## 🔄 Pagination Options

```bash
-n <count>               # Limit results
--all                    # Fetch all results
--max-pages <n>          # Max pages to fetch (requires --all or --cursor)
--cursor <string>        # Resume from cursor
--delay <ms>             # Delay between pages
```

## 🛠️ GraphQL Query IDs

X rotates GraphQL query IDs frequently. Bird auto-refreshes them when needed.

```bash
# Inspect cached query IDs
bird query-ids --json

# Force refresh query IDs
bird query-ids --fresh
```

**Cache location:** `~/.config/bird/query-ids-cache.json`
**Override:** `BIRD_QUERY_IDS_CACHE=/path/to/file.json`
**TTL:** 24 hours

Auto-recovery on 404 errors (invalid query ID).

## 📚 Library Usage

Use bird as a TypeScript library:

```typescript
import { TwitterClient, resolveCredentials } from '@steipete/bird';

// Initialize client
const { cookies } = await resolveCredentials({ cookieSource: 'safari' });
const client = new TwitterClient({ cookies });

// Search tweets
const searchResult = await client.search('from:username', 50);

// Fetch news
const newsResult = await client.getNews(10, { aiOnly: true });

// Fetch from specific tabs
const sportsNews = await client.getNews(10, {
  aiOnly: true,
  withTweets: true,
  tabs: ['sports', 'entertainment']
});

// Get account details
const aboutResult = await client.getUserAboutAccount('username');
if (aboutResult.success && aboutResult.aboutProfile) {
  console.log(aboutResult.aboutProfile.accountBasedIn);
  console.log(aboutResult.aboutProfile.createdCountryAccurate);
}
```

## 💡 Common Workflows

### Extract bookmarked threads with full context
```bash
bird bookmarks --all --full-chain-only --include-parent --json > bookmarks.json
```

### Search user's recent tweets about topic
```bash
bird search "from:username topic" -n 50 --json
```

### Get trending AI news with related tweets
```bash
bird news --ai-only --with-tweets --tweets-per-item 5 -n 20 --json
```

### Export all followers
```bash
bird followers --all --json > followers.json
```

### Read thread with all replies
```bash
bird thread <tweet-id> --all --json
```

## ⚡ Quick Reference

### Repository Info
- **Homepage:** None
- **Open Issues:** 1
- **Last Updated:** 2026-02-08
- **Primary Language:** TypeScript (99.8%)

## ⚠️ Known Issues

*Recent issues from GitHub*

- **#1**: make an empty issue to avoid skill-seekers error

*See `references/issues.md` for complete list*

### Recent Releases
No releases available

## 📖 Available References

- `references/README.md` - Complete README documentation (389 lines)
- `references/CHANGELOG.md` - Version history and changes
- `references/issues.md` - Recent GitHub issues
- `references/file_structure.md` - Repository structure

## 🎯 Exit Codes

- `0` - Success
- `1` - Runtime error (network/auth/etc)
- `2` - Invalid usage/validation (e.g., bad `--user` handle)

---

**Generated by Skill Seeker** | GitHub Repository Scraper
**Enhanced with comprehensive command reference and usage examples**
