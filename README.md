# SahamYar

SahamYar is an Android application and Python backend for intelligent analysis
of Iran's capital market. The project combines market/instrument data,
technical indicators, Codal financial disclosures and market-calendar
information. Its broader product direction includes macroeconomic, news,
geopolitical, liquidity and global/parallel-market evidence.

The system must distinguish source facts, deterministic calculations and
AI interpretation. Missing or stale data must remain explicitly unavailable;
the application must not invent values or produce a complete-looking signal
when evidence is insufficient.

## Product scope

Included:
- Search and analysis of Iranian market instruments.
- Technical analysis where the instrument type and input data support it.
- Codal disclosure discovery and financial-statement parsing/standardization.
- Market status and calendar information.
- Evidence-based analysis with explicit uncertainty and risk as capabilities
  are completed.

Explicitly out of scope:
- Personal portfolio management.
- Recording user transactions or calculating personal cost basis/profit/loss.
- Importing personal transactions from Excel.
- Brokerage order placement or automatic trading.

## Repository layout

- app/: Android application (Kotlin, Jetpack Compose).
- backend/: Flask API, TSETMC/Codal providers, analysis services and tests.
- AGENTS.md: engineering and safety rules for the repository.
- STATUS.txt: verified project snapshot and known limitations.
- ROADMAP_DEFERRED.md: planned work that is not yet complete.
- HISTORY.md: dated project decisions and verification history.
- TERMUX_COMMANDS.md: local Termux development/test commands.
- Handoff Document.txt: current engineering handoff.

## Technology

### Android
- Kotlin and Jetpack Compose.
- Retrofit/OkHttp for HTTP API access.
- Room for local persistence.
- Application ID: com.techquantum.sahamyar.
- Current version: 1.0.0 (versionCode 1).
- compileSdk/targetSdk: 36; minSdk: 26; JVM target: 17.

### Backend
- Python 3.11 or newer.
- Flask 3.x, httpx, tzdata and persiantools.
- pytest and Ruff for development/testing.
- TSETMC provider for market instruments and price history.
- Codal client/parser for disclosures and financial statements.

## Current backend capabilities

- TSETMC instrument search and instrument details.
- Latest/cached prices and daily price history.
- Instrument category metadata; search coverage is distinct from analytical
  support. Current technical-analysis route supports COMMON_STOCK and RIGHTS
  only where provider mapping validates the category.
- Technical indicators: SMA, EMA, RSI, MACD, Bollinger Bands, ATR, Stochastic,
  OBV, volume SMA and volume ratio.
- Codal financial-report discovery, retrieval, parsing of five financial
  statement structures and metric standardization.
- Market-hours and Jalali-year calendar handling.
- Overall market status, market-scoped calendar status and instrument-scoped
  market status.
- In-memory price cache and background refresh scheduler.
- Sanitized public provider errors.

## Local development in Termux

Repository path used in the current workflow:

    cd ~/SahamYar/repo-check

### Backend setup and tests

    cd backend
    python -m pip install -e '.[dev]'
    python -m pytest -q

Run the local API:

    python -m app.main

The development server listens on 127.0.0.1:8000. The module entry point
starts the in-process price scheduler. Importing the Flask app through a WSGI
server does not execute that entry point; production worker lifecycle and
multi-process scheduler coordination must be designed separately.

### Android tests and debug APK

From the repository root:

    ./gradlew testDebugUnitTest --rerun-tasks
    ./gradlew assembleDebug

The debug APK is normally written to:

    app/build/outputs/apk/debug/app-debug.apk

The current Retrofit base URL is http://127.0.0.1:8000/, intended for
same-device local development where the backend is reachable on that device.
Do not change it without validating the actual network topology and testing
the Android-to-backend connection.

More Termux commands are documented in [TERMUX_COMMANDS.md](TERMUX_COMMANDS.md).

## API

All routes below are served by the Flask backend.

| Method | Route | Purpose |
|---|---|---|
| GET | /health | Backend liveness |
| GET | /api/v1/market/status | Overall market and calendar status |
| GET | /api/v1/markets/{market}/status | Market-scoped calendar status |
| GET | /api/v1/stocks/search?q={query} | Search TSETMC instruments |
| GET | /api/v1/stocks/{ins_code} | Instrument details |
| GET | /api/v1/stocks/{ins_code}/market-status | Instrument-scoped market/calendar status |
| GET | /api/v1/stocks/{ins_code}/prices | Cached latest price data |
| GET | /api/v1/stocks/{ins_code}/history?count={n} | Daily price history |
| GET | /api/v1/stocks/{ins_code}/analysis?count={n} | Technical indicators and analysis-layer status |
| GET | /api/v1/stocks/{ins_code}/financial-reports?page={n} | Search Codal financial reports |
| GET | /api/v1/stocks/{ins_code}/financial-reports/{tracing_no}?page={n} | Retrieve and standardize a selected report |

The financial-report detail route uses the instrument code and the exact
Codal tracing number; the page parameter identifies the report-search page
used to locate that report.

## Data and analysis policy

- Missing values remain null/absent; never replace them with zero.
- Preserve source, retrieval time, reference date, units and report metadata.
- Distinguish AVAILABLE, PARTIAL, UNAVAILABLE, INSUFFICIENT_DATA,
  UNSUPPORTED and ERROR.
- A cached value must be labeled as cached and carry its timestamp.
- Never infer live economic, geopolitical or market data from model memory.
- A technical indicator alone is not a complete BUY/SELL/HOLD recommendation.
- Recommendations require adequate evidence, reasons, uncertainty, scenarios
  and risks.

## Current limitations

- Codal statement parsing/standardization exists, but a complete fundamental
  ratios engine, comparable multi-period analysis and fundamental scoring are
  not complete.
- News, Iran macroeconomic, geopolitical, liquidity/flow and global-market
  providers are not fully connected and verified. Corresponding layers must
  remain unavailable/partial until reliable current data is supplied.
- The analysis API currently returns INSUFFICIENT_DATA for its recommendation
  action while the wider evidence set is incomplete. A complete recommendation
  engine must not be claimed yet.
- Price cache, subscriptions and scheduler state are in-memory.
- Durable watchlist/alert storage and authenticated user-specific APIs are
  not complete.
- The scheduler starts from python -m app.main; WSGI imports do not start it.
  Multi-worker coordination is not complete.
- The API does not yet provide a complete authentication/authorization layer.
- Successful compilation and unit tests do not replace full device-level
  Android/backend integration tests.
- Production deployment is deferred.

## Verification snapshot (2026-11-28)

- Backend test suite: 469 passed.
- Android unit-test task forced with --rerun-tasks: BUILD SUCCESSFUL
  (26 Gradle tasks executed; the captured summary did not report a test-case count).
- Android debug APK build: BUILD SUCCESSFUL.
- GitHub Actions run #38 on the main baseline completed successfully for
  Backend Tests and Android Debug Build.

These are dated results. Re-run tests after code changes; see STATUS.txt
for the full snapshot and ROADMAP_DEFERRED.md for unfinished work.
