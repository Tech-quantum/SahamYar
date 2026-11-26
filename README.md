# SahamYar Backend

Backend services for researching the Iranian capital market. The committed codebase uses Flask, synchronous HTTP providers for TSETMC, an in-memory price cache, and **offline** Codal HTML parsing/standardization.

Repository snapshot checked: main at 97107538c42fb0548a367971c540591efc6d663d (2026-11-26).

## Current capabilities (verified on main)
- TSETMC instrument search, instrument details, current/closing price data, and daily price history.
- Instrument classification; technical analysis is restricted to common stocks and rights where supported.
- SMA, EMA, RSI, and MACD calculations.
- Market-session-aware price caching and a background refresh scheduler (started only from the module __main__ block).
- Offline Codal financial-statement HTML parsing for five statement types and metric standardization without guessing ambiguous labels.

## Not implemented on main (do not advertise as live API)
- HTTP Codal company/report client wired into Flask routes
- GET /api/v1/codal/companies
- GET /api/v1/codal/reports
- GET /api/v1/codal/reports/{tracing_no}/financial-statements
- Stock-level financial-reports endpoints
- Fundamental layer population inside /analysis (always UNAVAILABLE)
- Accounting ratios engine, cross-period fundamental scoring, news/macro/geo feeds

If local worktree contains additional Codal HTTP code, treat it as unpushed until it appears on the remote branch and tests pass.

## Run locally
Python 3.11 or newer is required.
```bash
cd backend
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m app.main
```
Development server: 127.0.0.1:8000. For production, use a WSGI server and manage background workers explicitly.

## Tests
```bash
cd backend
python -m pytest -q
```

## API routes (implemented in app/main.py)
| Method | Route | Purpose |
|---|---|---|
| GET | /health | Liveness check |
| GET | /api/v1/stocks/search?q= | Search TSETMC instruments |
| GET | /api/v1/stocks/{ins_code} | Instrument details |
| GET | /api/v1/stocks/{ins_code}/prices | Cached latest price information |
| GET | /api/v1/stocks/{ins_code}/history?count= | Daily price history |
| GET | /api/v1/stocks/{ins_code}/analysis?count= | Technical indicators and layer availability |

## Configuration
| Variable | Default | Description |
|---|---|---|
| APP_NAME | SahamYar API | Service display name |
| APP_ENV | development | development or production |
| TSETMC_BASE_URL | https://cdn.tsetmc.com/api | TSETMC API base URL |
| TSETMC_TIMEOUT_SECONDS | 20.0 | Upstream request timeout |
| TSETMC_MIN_INTERVAL_SECONDS | 1.0 | Minimum spacing between TSETMC requests |
| TSETMC_MAX_RETRIES | 2 | Retry count for transient upstream errors |

## Important limitations
- Codal parsing exists; live Codal HTTP integration and fundamental scoring are not committed on main.
- News, macroeconomic, geopolitical, and global-market layers must remain UNAVAILABLE until real providers are connected.
- Price subscriptions are in-memory only.
- The price scheduler starts in python -m app.main only; multi-worker WSGI deployments need an explicit worker design.
- No authentication/authorization layer yet.
