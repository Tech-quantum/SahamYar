# SahamYar Project History

## 2026-11-15 - Initial product planning
Initial discussions included portfolio and transaction-management ideas.
These were later superseded by the narrower product scope.

## 2026-11-17 - Confirmed product scope
SahamYar was defined as an intelligent Iranian capital-market analysis assistant.
Personal portfolio management, transaction entry, personal profit/loss,
Excel transaction imports and automatic trading were excluded.

Instrument categories were clarified:
- COMMON_STOCK
- RIGHTS
- FUND
- DEBT
- OTHER

A sample alert scenario was documented:
Foolad (فولاد), trigger when price rises above 13,000 Rial.
This is a test example, not a live quote or recommendation.

## 2026-11-17 to 2026-11-20 - Backend review
TSETMC search and instrument classification were reviewed.
Codal financial report parsing and normalization were examined.
Five financial statement types were identified:
income_statement, comprehensive_income, balance_sheet,
equity_changes and cash_flow.

Parser behavior was tested against a real Foolad report sample.
That single sample does not prove compatibility with every Codal layout.

## 2026-11-20 - Price and scheduler hardening
A price-cache and scheduler hardening patch was applied locally.
A previous test run reported 249 passing backend tests.
That result was a historical snapshot and was later superseded by the
469-test verification recorded below.

## 2026-11-21 - Audit and handoff
The project audit identified further review priorities:
Codal retry behavior, response-size limits, date validation,
API error sanitization, technical-indicator data sufficiency,
and scheduler shared-state design.

## 2026-11-22 to 2026-11-27 - Backend and Android integration foundation
The project gained additional backend and Android implementation work,
including market-calendar/status capabilities, instrument-scoped market
status, expanded API coverage, and Android application/build configuration.
The root README and engineering guidance were brought into the main branch.
See the source tree and tests for the exact implemented behavior; this history
entry does not imply that every planned analysis layer is complete.

## 2026-11-28 - Main branch synchronization and verification
The local Termux main branch was fast-forwarded to the GitHub main baseline:
37bcf9df04ce9b2a8a8b417cd60fe677218e43f3.

Verified results on that snapshot:
- Backend: 469 tests passed in 3.27 seconds.
- Android: ./gradlew testDebugUnitTest --rerun-tasks completed successfully;
  Gradle reported 26 actionable tasks executed. The captured summary did not
  include a test-case count.
- Android: ./gradlew testDebugUnitTest assembleDebug completed successfully
  and assembled the debug APK. The unit-test task was up-to-date in that run;
  the forced test rerun is recorded separately above.
- GitHub Actions run #38 on main completed successfully for Backend Tests and
  Android Debug Build.

The Android SDK manager emitted repository-manifest download warnings during
local Gradle execution; they did not prevent the reported successful tasks.

At the last local status check, two untracked files were preserved and were
not part of the tracked main snapshot: app.py and
settings.gradle.kts.before-aliyun.

## Persistent engineering principles
- Preserve local changes and untracked files.
- Never commit, push or merge without explicit approval.
- Never use destructive Git commands without explicit approval.
- Missing data is not zero.
- Separate source facts, calculations and AI interpretation.
- Make unsupported capabilities explicit.
- Verify current source and tests before claiming implementation status.
- Keep documentation synchronized with the code and clearly date verification.
