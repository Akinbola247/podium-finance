# Podium Finance

**Bloomberg-style whale tape + quant profiles + risk-bounded execution plans — built for Injective and Helix.**

---

## What Podium Finance does

On Injective, meaningful trading flow is buried in raw explorer transactions: nested `MsgExec` batches, perp margin updates, spot swaps, and transfers all look the same at a glance. Podium Finance **watches the wallets you care about**, ingests their **live mainnet Helix activity**, and turns it into something you can actually trade research with:

1. **See what happened** — A structured whale tape: asset, side (long/short open/close), fill price, USD notional, and estimated P&L per event.
2. **Understand who is worth watching** — Live **Discover** scans the chain for active perp/spot traders (not INJ stakers), ranks them by volume and clip quality, and lets you import them to a watchlist.
3. **Quantify behavior** — Per-wallet conviction score, win-rate proxy, FIFO realized P&L, portfolio mix, and strategy fingerprint (momentum vs mean-reversion vs LP-heavy).
4. **Get notified when it matters** — Smart alerts fire on anomaly clips (new asset, size vs wallet history), pushed over WebSocket in near real time.
5. **Frame your own risk** — For any event, generate an **execution blueprint**: Kelly-damped sizing, stop/take-profit bands, and caps tied to *your* portfolio and drawdown tolerance — educational analytics, not auto-trading.


---

## Why DeFi folks should use it

| If you are… | Podium helps you… |
|-------------|-------------------|
| **Helix / Injective perp or spot trader** | Catch large clips and bias shifts before they show up in social channels; filter noise from real exchange flow. |
| **On-chain researcher or fund analyst** | Build a watchlist of counterparties, compare conviction and P&L style, export a repeatable view of *exchange* behavior (not staking or bridge dust). |
| **Trader learning from “smart money”** | Read AI summaries and quant context on each fill instead of guessing from a tx hash in the explorer. |
| **Risk-conscious participant** | Translate “whale opened $800k BTC perp” into “what size fits *my* book?” without Telegram hype sizing. |

**Compared to the default toolchain:**

- **Block explorer** — Shows messages, not positions: you still decode ticks, markets, and batch orders yourself.
- **Staking dashboards / whale lists** — Often rank **INJ stakers**, not **Helix traders**; Podium’s Discover and filters target copy-relevant flow.
- **Generic multi-chain trackers** — Rarely decode Injective exchange modules or Helix market IDs; Podium is **Injective-native** (registry, ticks, `MsgBatchUpdateOrders`, authz exec).
- **Copy-trading bots** — Execute for you and blur risk; Podium stays **read-only analytics** with explicit compliance framing.

Podium does **not** replace your wallet or exchange. It is a **research and alerting layer** on top of public chain data.

---

## Why this product matters now

**Injective + Helix** sit at the intersection of Cosmos execution and centralized-orderbook perps: flow is on-chain, fast, and increasingly multi-asset (BTC, ETH, alts), but **liquidity and positioning are still concentrated in identifiable wallets**. For DeFi participants, that creates a gap:

- **Alpha is on-chain**, yet most tools still present **accounts**, not **trades**.
- **Perp-heavy ecosystems** reward timing and size discipline; without clip-level history, “following whales” is guesswork.
- **Regulatory and safety pressure** pushes users away from blind copy-trade; they need **interpretation + risk bounds**, not another signal group.

Podium is relevant because it treats Injective whale-watching as a **professional workflow**: discover traders → track → alert → quantify → size hypothetically. That matches how serious DeFi desks actually work, while staying honest about data limits (oracle marks, estimated P&L, educational-only blueprints).

**Who it is not for:** users who want one-click copy execution, guaranteed returns, or chain-agnostic portfolio tracking. **Who it is for:** Injective natives who believe **order flow is the product** and want infrastructure to read it.

---

## How it works (technical)

**Live data only** — Prefer **Discover** for finding active Helix traders; static JSON bulk-import APIs are ops-only ([`docs/DATA_AUDIT.md`](docs/DATA_AUDIT.md)).

### Architecture

```text
Injective Explorer API
        │
        ▼
stream worker ──► tx decoder + market registry + price oracle
        │              │
        │              ▼
        │         SQLite (watched wallets, whale_activity)
        │              │
        │              ├── quant analysis (FIFO P&L, conviction)
        │              └── smart alert rules
        ▼
Redis pub/sub (podium:live_alerts)
        │
        ▼
FastAPI (REST + WebSocket) ──► Next.js dashboard
```

| Component | Role |
|-----------|------|
| **Stream worker** | Polls global + per-wallet txs; ingests, alerts, publishes |
| **Tx decoder** | Helix spot/derivative orders, bank sends, LP; authz `MsgExec` flattening |
| **Market registry** | LCD spot + derivative markets → tickers, tick sizes, base assets |
| **Price oracle** | CoinGecko USD marks; oracle-validated notionals |
| **Redis** | Dedup, price cache, live alert channel |
| **Frontend** | Dashboard, Discover, Watchlist, per-wallet profiles |

---

## Features

### Live ingestion & decoding

- **Explorer-backed ingestion** — `txs` stream + `accountTxs/{address}` backfill on watchlist add
- **Multi-asset Helix coverage** — decodes spot and perpetual markets via on-chain market IDs (BTC, ETH, INJ, alt perps, etc.)
- **Activity types** — `SWAP`, `MARGIN_POSITION_OPEN`, `MARGIN_POSITION_CLOSE`, `LIQUIDITY_PROVISION`, `LARGE_TRANSFER`
- **Nested transactions** — unwraps `/cosmos.authz.v1beta1.MsgExec` and `MsgBatchUpdateOrders` (create + cancel batches)
- **Oracle-validated USD notionals** — `price × qty` when ticks decode cleanly; adjusts only when implied price is far from CoinGecko (not a flat cap)
- **Deduplication** — Redis `podium:seen:{tx_hash}` prevents double-ingest
- **Configurable floors** — `MIN_NOTIONAL_USD`, `LARGE_TRANSFER_USD` for dust and alert thresholds

### Wallet watchlist

- Track native **`inj1…`** addresses only (validators `injvaloper…` and `0x…` rejected with clear errors)
- Optional **alias** and **risk category** (`conservative` | `moderate` | `aggressive`)
- **Automatic backfill** when a wallet is added or imported
- **Watchlist sync** — re-queue backfill for all tracked wallets (e.g. after DB reset)
- **Scrollable sidebar** on the dashboard for long watchlists; add-wallet form pinned at the bottom

### Discover (live whale scan)

- **Real-time mainnet scan** — paginated global tx poll; filters to copy-relevant Helix fills (not stakers or idle transfers)
- **Scoring & tiers** — volume, event count, clip size, multi-asset bias; copyability tiers **A / B / C / D**
- **Configurable criteria** — min notional, min exchange events/volume, largest clip, multi-asset preference, exclude existing watchlist
- **Cached results** (~1 hour) via `search_id` for bulk **import to watchlist** with live backfill queued
- **UI** — scan table, selection, import success banner, “on watchlist” badges

### Dashboard (landing)

- **Live alerts strip** — WebSocket-driven smart alerts with stream status (connecting / live / reconnecting)
- **Metrics row** — conviction gauge, win rate / P&L stats, portfolio donut, P&L sparkline for selected whale
- **Whale tape** — sortable activity table with side badges, fill price, notional, realized/unrealized P&L column
- **Filters** — wallet, side (long / short / swap), asset
- **Risk execution blueprint** — slide-over panel on event select; Kelly-damped sizing, stop bands, disclaimers
- **Deep links** — `/?wallet=inj1…` pre-selects a watched address

### Quantitative analysis

- **30-day rolling metrics** — conviction score `0.4·Wr + 0.35·Sd + 0.25·Ht` (win rate, size discipline, holding time)
- **FIFO fill ledger** — realized P&L on closes; unrealized marks on open exposure
- **Per-event enrichment** — fill price, execution side (`LONG_OPEN`, `SHORT_CLOSE`, etc.), P&L kind on feed rows
- **Strategy fingerprint** — `MOMENTUM`, `YIELD_FARMING`, `MEAN_REVERSION`, or `UNCLASSIFIED` from recent activity mix
- **Wallet quant API** — win rate %, profit factor, directional bias (`ACCUMULATING` / `DISTRIBUTING`), per-asset breakdown, recent fills

### Smart alerts

- **Anomaly rules** — new asset on wallet, exchange clip vs historical median, 2× median spike
- **Urgency tier** — derived from notional (HIGH / MEDIUM / LOW), not hardcoded stubs
- **Confidence metric** — higher when `injective_explorer_live` source and AI narrative present
- **Redis + WebSocket** — `podium:live_alerts` channel; WS bootstraps recent alerted events
- **REST fallback** — `GET /api/v1/alerts/recent`

### AI summaries

- **Rules-first narratives** — structural summary from activity type, asset, notional, block, message types
- **Optional OpenAI** — `OPENAI_API_KEY` enhances `structural_narrative`, intent hypothesis, tier, confidence (still tied to real txs)
- **Trade conclusions** — contextual text for profiles and blueprint using quant + event fill data

### Risk execution blueprint

- **Event-specific plan** — user portfolio USD, max drawdown %, leverage cap
- **Kelly fraction** (damped) combined with conviction and whale notional tier
- **Stop-loss / take-profit bands** — ATR-based levels from direction and activity type
- **Educational framing** — hypothetical vs recommended allocation; compliance disclaimers in UI

### Whale profiles (`/profile/[address]`)

- Conviction gauge, P&L summary, portfolio distribution
- Recent activity with P&L where available
- Link back to dashboard with wallet pre-selected

### Ops / static imports (de-emphasized in UI)

- `POST /api/v1/watchlist/import-whales` — `data/injective_whale_addresses_inj1_only.json` (staker-heavy, poor copy signal)
- `POST /api/v1/watchlist/import-active-traders` — `data/injective_active_traders.json` (static snapshot)
- Responses include `data_source: static_snapshot` and warnings; activity still backfills from explorer

### Maintenance scripts

- `backend/scripts/recompute_notionals.py` — fix legacy rows stuck at the old $250k flat cap
- `backend/scripts/discover_active_traders.py` — regenerate static trader seed (ops)

---

## Frontend routes

| Route | Description |
|-------|-------------|
| `/` | Dashboard — watchlist sidebar, alerts, metrics, whale tape, blueprint panel |
| `/discover` | Live Helix trader discovery and watchlist import |
| `/watchlist` | Add wallet form + tracked list |
| `/profile/[address]` | Per-wallet analytics (watchlist members) |

Stack: **Next.js**, Tailwind, Framer Motion, Recharts, WebSocket stream context.

---

## Prerequisites

- Python 3.11+ (3.14 works with current deps)
- Node 20+
- **Redis 7+** (required for live alerts and dedup)

---

## Run locally (4 processes)

### 1. Redis

```bash
redis-server
# or: docker run -p 6379:6379 redis:7-alpine
```

### 2. Backend API

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional edits
uvicorn app.main:app --reload --port 8000
```

### 3. Stream worker (required for live ingestion)

```bash
cd backend
source .venv/bin/activate
python -m worker.stream_worker
```

### 4. Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env`:

```env
NEXT_PUBLIC_API_BASE=http://localhost:8000
NEXT_PUBLIC_WS_BASE=ws://localhost:8000
```

```bash
npm run dev
```

Open http://localhost:3000 · API docs http://localhost:8000/docs

---

## Docker Compose

```bash
docker compose up
```

Starts Redis, backend, worker, and frontend.

After major schema or notional logic changes, you may want to re-run backfill:

```bash
curl -X POST http://localhost:8000/api/v1/watchlist/sync
```

---

## Usage flow

1. **Discover** — scan mainnet for active Helix traders → import selected addresses, *or* add a wallet manually on **Watchlist** / dashboard sidebar.
2. **Backfill** runs automatically; historical txs appear in the whale tape.
3. **Worker** polls every ~12s (configurable); new txs publish over WebSocket when smart-alert rules pass.
4. Select a **wallet** in the sidebar (or filter) → review metrics and tape.
5. Click an **event** → open the **execution blueprint** slide-over → generate a risk-bounded plan.

Example address with recent Helix activity (for testing): `inj146szu6alq9r5l8fgw97sml7mn9vjrng8wdsatc`

---

## API reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Redis, DB counts, `data_source`, explorer URL |
| GET | `/api/v1/markets/summary` | Helix market registry stats (spot + perp) |
| GET | `/api/v1/watchlist` | List tracked wallets |
| POST | `/api/v1/watchlist` | Add wallet (+ background backfill) |
| POST | `/api/v1/watchlist/sync` | Queue backfill for all watchlist wallets |
| POST | `/api/v1/watchlist/import-whales` | Bulk import from static JSON (ops) |
| POST | `/api/v1/watchlist/import-active-traders` | Bulk import active traders JSON (ops) |
| POST | `/api/v1/whales/discover` | Live Helix trader scan |
| POST | `/api/v1/whales/discover/import` | Import from cached `search_id` |
| GET | `/api/v1/whales/activity` | Activity feed (`wallet_address`, `only_alerted`, pagination) |
| GET | `/api/v1/whales/profile/{address}` | Conviction, quant, portfolio distribution |
| GET | `/api/v1/alerts/recent` | Recent smart-alert payloads |
| WS | `/api/v1/alerts/ws` | Live alert stream (Redis-backed) |
| POST | `/api/v1/risk/execution-plan` | Risk blueprint for a whale event |
| POST | `/api/v1/internal/simulate-summary/{event_id}` | Re-run alert + summary (dev) |

Activity items include: `fill_price_usd`, `execution_side`, `realized_pnl_usd`, `unrealized_pnl_usd`, `pnl_kind`, `notional_adjusted`, `ai_interpretation`.

---

## Environment variables

See `backend/.env.example`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `INJECTIVE_EXPLORER_URL` | Mainnet sentry explorer | Tx + account history |
| `REDIS_URL` | `redis://localhost:6379/0` | Alerts, dedup, price cache |
| `REDIS_ALERTS_CHANNEL` | `podium:live_alerts` | Pub/sub channel name |
| `POLL_INTERVAL_SECONDS` | `12` | Worker poll interval |
| `GLOBAL_TX_BATCH_SIZE` | `40` | Global tx batch per cycle |
| `ACCOUNT_TX_BACKFILL_LIMIT` | `80` | History depth on add/sync |
| `WALLET_POLL_BATCH_SIZE` | `5` | Rotating per-wallet poll batch |
| `WALLET_POLL_TX_LIMIT` | `25` | Txs per wallet per poll |
| `MIN_NOTIONAL_USD` | `25` | Minimum ingest notional |
| `LARGE_TRANSFER_USD` | `500` | Smart-alert size threshold |
| `OPENAI_API_KEY` | (empty) | Optional LLM summaries |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model id |
| Discover `DISCOVER_*` | see `config.py` | Scan limits and filters |

Frontend: `NEXT_PUBLIC_API_BASE`, `NEXT_PUBLIC_WS_BASE`.

---

## Compliance

Copy and UI text are **educational analytics only** — not financial advice. No “copy trade,” guaranteed returns, or investment solicitation language. Execution blueprints are hypothetical risk frameworks, not trade instructions.

---

## Documentation

| Doc | Contents |
|-----|----------|
| [`docs/DATA_AUDIT.md`](docs/DATA_AUDIT.md) | Live vs static data paths, provenance, operator checklist |
| [`docs/PODIUM_FINANCE_UI_UX_BRIEF.md`](docs/PODIUM_FINANCE_UI_UX_BRIEF.md) | Product / UX brief |
| [`PODIUM_FINANCE_UI_PROMPT.md`](PODIUM_FINANCE_UI_PROMPT.md) | UI build spec |

---

## Project structure

```text
backend/
  app/              # FastAPI, ingestion, tx_decoder, quant_analysis, whale_discovery
  worker/           # stream_worker.py (run as separate process)
  scripts/          # recompute_notionals, discover_active_traders, etc.
frontend/
  app/              # Next.js routes (/, /discover, /watchlist, /profile/…)
  components/       # dashboard, feed, blueprint, discover, watchlist, charts
  context/          # WebSocket stream provider
data/               # Optional static address JSON (ops imports)
docs/
docker-compose.yml
```
