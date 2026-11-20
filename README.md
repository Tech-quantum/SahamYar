# SahamYar Backend

Backend services for researching the Iranian capital market. The current codebase
uses Flask, synchronous HTTP providers, an in-memory price cache, and offline
Codal HTML parsing.

## Current capabilities

- TSETMC instrument search, instrument details, current/closing price data, and
  daily price history.
- Instrument classification; technical analysis is currently restricted to
  common stocks and rights where explicitly supported by the provider mapping.
- SMA, EMA, RSI, and MACD calculations.
- Market-session-aware price caching and a background refresh scheduler.
- Codal company directory search, disclosure-letter search, safe report URL
  resolution, report HTML retrieval, five-statement HTML parsing, and financial
  metric standardization.

## Run locally

Python 3.11 or newer is required.

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m app.main
```

The local development server listens on `127.0.0.1:8000`. For a remote or
production deployment, run Flask through a production WSGI server and operate
background workers as separate processes; do not use Flask's development server.

## Tests

```bash
cd backend
python -m pytest -q
```

## API routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/api/v1/stocks/search?q=` | Search TSETMC instruments |
| GET | `/api/v1/stocks/{ins_code}` | Instrument details |
| GET | `/api/v1/stocks/{ins_code}/prices` | Cached latest price information |
| GET | `/api/v1/stocks/{ins_code}/history?count=` | Daily price history |
| GET | `/api/v1/stocks/{ins_code}/analysis?count=` | Technical indicators and analysis-layer availability |
| GET | `/api/v1/codal/companies?q=` | Search Codal companies by symbol/name |
| GET | `/api/v1/codal/reports?symbol=&page=` | Search a company's Codal disclosures |
| GET | `/api/v1/codal/reports/{tracing_no}/financial-statements?symbol=&page=` | Retrieve and standardize a matching report's financial statements |

The Codal financial-statement route requires the exact symbol and page on which
the tracing number was found. This avoids guessing a symbol-to-instrument mapping
or silently selecting a different disclosure.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `SahamYar API` | Service display name |
| `APP_ENV` | `development` | `development` or `production` |
| `TSETMC_BASE_URL` | `https://cdn.tsetmc.com/api` | TSETMC API base URL |
| `TSETMC_TIMEOUT_SECONDS` | `20.0` | Upstream request timeout |
| `TSETMC_MIN_INTERVAL_SECONDS` | `1.0` | Minimum spacing between TSETMC requests |
| `TSETMC_MAX_RETRIES` | `2` | Retry count for transient upstream errors |

## Important limitations

- Codal parsing and standardization are implemented, but accounting ratios,
  cross-period trend calculations, and a complete fundamental scoring engine
  are not yet implemented.
- News, macroeconomic, geopolitical, and global-market data providers are not
  connected yet. The analysis response must continue to report those layers as
  unavailable rather than infer data.
- Price subscriptions are currently in-memory. A durable watchlist/alert
  subscription store and authenticated subscription API are still required
  before the scheduler can refresh user-tracked symbols across restarts.
- The price scheduler is started by `python -m app.main`; WSGI deployments do
  not execute the module's `__main__` block. Production worker lifecycle and
  multi-process coordination must be designed before enabling scheduled refresh
  in a multi-worker deployment.
- The API currently has no user authentication/authorization layer. Do not
  expose write or subscription-management endpoints publicly until this is
  implemented.
- All upstream integrations require live-network verification in the target
  deployment environment.
