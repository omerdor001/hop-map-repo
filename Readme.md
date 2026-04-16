# HopMap - Game Changers

![Python](https://img.shields.io/badge/python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688)
![React](https://img.shields.io/badge/React-18+-61DAFB)
![MongoDB](https://img.shields.io/badge/MongoDB-7.0+-47A248)
![Ollama](https://img.shields.io/badge/Ollama-local--inference-black)
![Platform](https://img.shields.io/badge/platform-Windows-0078D4)
![Tests](https://img.shields.io/badge/tests-49%20passing-brightgreen)
![Maintained](https://img.shields.io/badge/maintained-yes-brightgreen)

A full-stack child safety platform that detects and alerts parents when children attempt to "hop" from moderated gaming environments to unmoderated external platforms in real time.

## 🎯 Overview

HopMap monitors a child's Windows gaming session and uses LLM-powered classification to detect **platform hopping** — when a child is lured from a supervised game to an unmoderated platform (Discord, Instagram, Telegram, etc.). The system includes:

- **Desktop Agent** — Lightweight Windows sensor using Win32 hooks, Tesseract OCR, and clipboard monitoring with no local LLM overhead
- **Classification Server** — FastAPI backend that runs Ollama locally for URL/context classification, keeping all AI inference off the child's machine
- **Blocked-Words Filter** — Aho-Corasick multi-pattern filter that intercepts known harmful words and phrases before any LLM call, supporting special characters (`18+`) and Unicode scripts (Hebrew)
- **Parent Dashboard** — React frontend with live SSE event streaming, child profiles, alert history, and whitelist/blacklist management
- **MongoDB Database** — Persistent storage for hop events, session history, per-child settings, whitelists, and blacklists
- **Test Suite** — 49 passing tests across unit and integration layers covering the filter engine, platform loader, classify endpoint, and words CRUD API

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.10+, Node.js 18+, MongoDB running locally or on Atlas
# Ollama desktop client installed and running
ollama pull llama3
```

### Setup & Run

1. **Configure the server** (copy and fill in your values):
   ```bash
   cd server
   cp .env.example .env
   # Set MONGO_URI, OLLAMA_MODEL, etc.
   ```

2. **Start the server**:
   ```bash
   cd server
   pip install -r requirements.txt
   uvicorn server:app --host 0.0.0.0 --port 8000
   ```

3. **Start the desktop agent** (on the child's Windows machine, in a new terminal):
   ```bash
   cd agent
   pip install -r requirements.txt
   python agent.py        # shows console — useful for debugging
   # pythonw agent.py     # hides console — recommended for production
   ```

4. **Start the dashboard** (in a new terminal):
   ```bash
   cd dashboard
   npm install
   npm run dev
   ```

5. **Open the parent dashboard**:
   Navigate to `http://localhost:5173` and add a child profile to begin monitoring.

## 📐 Architecture

```
┌──────────────────────┐        ┌─────────────────────────┐        ┌─────────────────┐
│  Kid's Gaming PC     │        │  HopMap Server           │        │  Parent Browser │
│                      │        │  (FastAPI :8000)         │        │                 │
│  Desktop Agent       │───────▶│  POST /agent/classify    │        │  React Dashboard│
│  - Win32 hook        │        │  POST /agent/hop/{id}    │───────▶│  GET /stream/   │
│  - OCR (Tesseract)   │        │  GET  /stream/{child_id} │  SSE   │  {child_id}     │
│  - Clipboard monitor │        │  REST /api/*             │        │                 │
└──────────────────────┘        └────────────┬────────────┘        └─────────────────┘
                                             │
                                             ▼
                                   ┌─────────────────┐     ┌──────────────────┐
                                   │  Ollama (local) │     │  MongoDB         │
                                   │  LLM inference  │     │  - hop_events    │
                                   │  qwen2.5:7b     │     │  - children      │
                                   │  (or llama3)    │     │  - settings      │
                                   └─────────────────┘     └──────────────────┘
```

### Component Flow

1. **Agent** detects a candidate URL via OCR screenshot, clipboard poll, or window title
2. **Agent → Server** sends context snippet to `POST /agent/classify`; server runs the local Ollama model and returns `{ decision, confidence, reason }`
3. **Agent** observes the subsequent app-switch and confirms the hop tier (`app_match`, `title_match`, or `switch_only`)
4. **Agent → Server** reports the confirmed hop via `POST /agent/hop/{child_id}`; server persists the event to MongoDB
5. **Server → Dashboard** pushes the event over SSE to all connected parent browsers watching that child

## 📁 Project Structure

```
hop-map-repo/
├── agent/                          # Windows desktop sensor
│   ├── agent.py                    # Main agent — Win32 hooks, OCR, clipboard, classification
│   ├── config.py                   # Agent configuration (server URL, thresholds)
│   ├── agent_config.json           # Runtime config (loaded by config.py)
│   └── requirements.txt
│
├── server/                         # FastAPI classification & event server
│   ├── server.py                   # App entry point — all routes and SSE streaming
│   ├── db.py                       # MongoDB connection pool & repository helpers
│   ├── config.py                   # Server configuration (env-var driven)
│   ├── colors.py                   # Terminal colour helpers
│   ├── words_filter.py             # Aho-Corasick multi-pattern blocked-words filter
│   ├── server_config.json          # Runtime config (loaded by config.py)
│   ├── requirements.txt
│   ├── data/
│   │   ├── hopmap_words_db.xlsx    # Blocked words & phrases source (seeded into MongoDB)
│   │   └── platforms_db.xlsx       # Platform → process mappings (served to agents)
│   ├── llm/                        # LLM provider abstraction
│   │   ├── __init__.py             # Factory — get_provider()
│   │   ├── base.py                 # Abstract LLMProvider base class
│   │   └── ollama_provider.py      # Ollama local inference (qwen2.5:7b / llama3)
│   └── tests/
│       ├── conftest.py             # Shared fixtures (live server, file paths)
│       ├── test_helpers.py         # Shared test utilities
│       ├── unit_tests/
│       │   ├── test_words_filter.py    # check_blocked_words() unit tests
│       │   ├── test_platforms_loader.py
│       │   └── words_db_tests.py       # Manual integration tests (requires live server)
│       └── integration_tests/
│           ├── test_classify_endpoint.py
│           └── test_words_endpoints.py
│
├── dashboard/                      # React parent dashboard (Vite)
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx                 # Root component — routing & child state
│       ├── main.jsx
│       ├── components/
│       │   ├── Homepage.jsx        # Live event timeline + SSE connection
│       │   ├── Kids.jsx            # Child profile management
│       │   ├── Alerts.jsx          # Alert history with date filtering
│       │   ├── Sidebar.jsx         # Navigation sidebar
│       │   └── settings.jsx        # Per-child settings, whitelist, blacklist
│       └── utils/
│           └── eventHelpers.jsx    # Shared formatters and icon helpers
│
└── Readme.md
```

## 🔧 Components

### 1. Desktop Agent (`agent/`)

A lightweight Windows-only sensor that runs on the child's PC. It performs no LLM work locally — all classification is delegated to the server, keeping gaming performance unaffected.

**Detection Pipeline:**

| Layer | Mechanism | Description |
|-------|-----------|-------------|
| Layer 0 | Win32 `SetWinEventHook` | Fires on every foreground-window change; raw HWNDs are queued and returned immediately |
| Layer 1 | Event-processor thread | Drains the HWND queue; drives scanner lifecycle and hop confirmation logic |
| Layer 2 | OCR scanner (Tesseract + mss) | Periodically screenshots the active game window and extracts URL candidates |
| Layer 3 | Clipboard monitor | Polls the system clipboard every second — catches "copy this link" lures invisible to OCR |
| Layer 4 | Server classification | POSTs each new URL (TTL-deduplicated) to `/agent/classify`; skips gracefully if server is unreachable |
| Layer 5 | Hop confirmation | On app-switch away from the game, assigns one of three click-confidence tiers |

**Confirmation Tiers:**

| Tier | Signal |
|------|--------|
| `app_match` | The native desktop app for the lure platform opened |
| `title_match` | A browser navigated to the lure domain (title poll) |
| `switch_only` | An app switch occurred but no stronger signal was available |

### 2. Classification Server (`server/`)

A FastAPI application that runs on the parent's network. It exposes endpoints for the agent, a real-time SSE stream for the dashboard, and REST management APIs.

**Blocked-Words Filter (`server/words_filter.py`):**

Before every LLM call, the server scans the context snippet through a `WordsFilter` backed by an [Aho-Corasick](https://en.wikipedia.org/wiki/Aho%E2%80%93Corasick_algorithm) automaton. This catches known bad phrases and words in a single O(n) pass — no regex tokenization, correct for all character sets including Hebrew and special-char entries like `18+`. Only if no match is found does the request proceed to Ollama.

**Key Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/agent/classify` | Classify a URL + context snippet with the local Ollama model |
| `POST` | `/agent/hop/{child_id}` | Record a confirmed hop event for a child |
| `GET` | `/stream/{child_id}` | Server-Sent Events stream of live hop events for the dashboard |
| `GET` | `/health` | Server and database health check |
| `GET` | `/api/children` | List all registered child profiles |
| `POST` | `/api/children` | Register a new child profile |
| `PATCH` | `/api/children/{child_id}` | Rename an existing child |
| `GET` | `/api/events/{child_id}` | Fetch hop event history for a child |
| `DELETE` | `/api/events/{child_id}` | Clear all stored events for a child |

**Key Features:**
- Per-child async rate limiter prevents agent flooding of the classifier
- Ollama runs entirely on the server — zero AI load on the child's gaming machine
- SSE push ensures the parent dashboard updates instantly without polling
- MongoDB connection pool with graceful startup fallback

### 3. LLM Provider (`server/llm/`)

A pluggable provider abstraction for classification inference.

| Module | Description |
|--------|-------------|
| `base.py` | Abstract `LLMProvider` with `classify(context, system_prompt) → dict` |
| `ollama_provider.py` | Calls a locally running Ollama model (`qwen2.5:7b` default); returns `{ decision, confidence, reason }` |
| `__init__.py` | `get_provider()` factory — selects provider from `OLLAMA_MODEL` env-var |

The classification prompt catches explicit URLs, bare platform usernames, and invitation-style phrasing ("DM me on insta") — not just raw links.

### 4. Parent Dashboard (`dashboard/`)

A React + Vite single-page application for parents.

**Key Views:**

| Component | Description |
|-----------|-------------|
| `Homepage.jsx` | Live event timeline connected via SSE; date-filtered history; child selector |
| `Kids.jsx` | Add, rename, and manage child profiles |
| `Alerts.jsx` | Full alert history with event details and timestamps |
| `settings.jsx` | Per-child settings page (currently empty, reserved for future configuration) |
| `Sidebar.jsx` | Navigation and active-child indicator |

## ⚙️ Configuration

### Server Configuration

Create `server/.env` from `.env.example`:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server HTTP port |
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string (local or Atlas) |
| `DB_NAME` | `hopmap` | MongoDB database name |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Ollama model tag for classification (e.g. `llama3`, `mistral`, `gemma3` — or any model you have pulled locally) |

> To use MongoDB Atlas instead of a local instance, set `MONGO_URI` to your Atlas connection string — no other changes required.

### Agent Configuration

Create `agent/.env` from `.env.example`:

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_URL` | `http://localhost:8000` | HopMap server base URL |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Ollama model tag (fallback, if server is unreachable) |
| `SCAN_INTERVAL_SECONDS` | `5` | How often to OCR-scan the game window for links |
| `CONTEXT_LINES` | `10` | Chat lines around a detected URL sent to the classifier |

## 🧪 Testing

The server has a full test suite with **49 tests** across unit and integration layers, all passing with 0 expected failures.

### Running Tests

```bash
cd server
pip install -r requirements.txt
python -m pytest tests/ -v
```

### Test Structure

```
server/tests/
├── conftest.py                          # Shared fixtures (live server, data file paths)
├── test_helpers.py                      # Shared test utilities and constants
├── unit_tests/
│   ├── test_words_filter.py             # check_blocked_words() — 19 tests
│   ├── test_platforms_loader.py         # Platform DB loader — 11 tests
│   └── words_db_tests.py               # Manual integration tests (requires live server)
└── integration_tests/
    ├── test_classify_endpoint.py        # /agent/classify endpoint — 4 tests
    └── test_words_endpoints.py         # /api/words CRUD — 9 tests
```

### Test Categories

| Category | File | Tests | Description |
|----------|------|-------|-------------|
| Words filter unit | `test_words_filter.py` | 19 | `check_blocked_words()` with injected word sets; includes phrase matching, boundary checks, Unicode, and real-DB spot checks |
| Platforms loader unit | `test_platforms_loader.py` | 11 | `_load_platforms_db()` with synthetic Excel fixtures and the real file |
| Classify endpoint | `test_classify_endpoint.py` | 4 | Full HTTP flow: word-DB fast path (`via=word_db`), LLM fallback path, `18+`, and Hebrew |
| Words endpoints | `test_words_endpoints.py` | 9 | `/api/words` CRUD: add, duplicate, normalise, delete, reload |
| **Total** | | **49** | **0 expected failures** |

### Example Test Scenarios

**Word-boundary protection** — `hack` is blocked but `hackle` is not:
```python
def test_blocked_word_inside_longer_word_not_matched(self, monkeypatch):
    _set_words(monkeypatch, {"hack"})
    found, _ = check_blocked_words("hackle is a word about feathers")
    assert found is False
```

**Special-char entry (`18+`)** — previously xfail, now passing via Aho-Corasick:
```python
def test_18plus_blocked(self):
    found, _ = check_blocked_words("check out this 18+ content")
    assert found is True
```

**Hebrew blocked phrase** — prefix-attached Hebrew matched correctly:
```python
def test_hebrew_blocked_word_in_discord_context(self, live_server, child_id):
    res = requests.post(f"{live_server}/agent/classify",
        json={"context": "בוא לדיסקורד שלי אחי", ...})
    assert res.json()["via"] == "word_db"
```

**Longest-match wins** — more specific phrase takes priority over a shorter contained word:
```python
def test_longest_phrase_matched_first(self, monkeypatch):
    _set_words(monkeypatch, {"tell your parents", "don't tell your parents"})
    found, matched = check_blocked_words("please don't tell your parents about this")
    assert matched == "don't tell your parents"  # longer phrase wins
```

**Live server fixture** — integration tests spin up a real FastAPI + uvicorn instance on a free port, run the tests, then tear it down. No mocks, no hardcoded ports:
```python
@pytest.fixture(scope="session")
def live_server():
    port = find_free_port()
    thread = threading.Thread(target=uvicorn.run, kwargs={...}, daemon=True)
    thread.start()
    # wait for ready, yield base URL, cleanup on session end
```

---

## 🛡️ Security Notice

- **Local LLM Only** — All AI inference runs on the server machine; no data is sent to third-party AI services
- **No Cloud Dependency** — Works fully offline on a local network (Ollama + local MongoDB)
- **Minimal Agent Footprint** — The desktop agent sends only small context snippets (a few lines of chat + detected URL), not full screen captures
- **Rate Limiting** — A per-child async rate limiter is enforced on the classify endpoint to prevent abuse
- **Graceful Degradation** — If the server is unreachable, the agent treats URLs as safe and skips them rather than blocking the child's session

## 📦 Dependencies

```
# Server
fastapi
uvicorn[standard]
ollama
pymongo>=4.6.0
python-dotenv
pydantic>=2.0.0
pyahocorasick>=1.4.0

# Agent (Windows only)
pywin32
psutil
requests
python-dotenv
mss
pytesseract
Pillow
pyperclip

# Frontend
react >= 18
vite
```

**External tools:**
- [Ollama](https://ollama.com/) — Local LLM runtime (must be installed and running on the server machine)
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) — Required on the agent machine for screenshot-based detection

**Python Requirements:** >= 3.10

