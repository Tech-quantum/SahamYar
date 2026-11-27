# SahamYar Project History

## 2026-11-15 - Initial product planning
Initial discussions included portfolio and transaction-management ideas.
These were later superseded by the narrower product scope.

## 2026-11-17 - Confirmed product scope
SahamYar was defined as an intelligent Iranian stock-market analysis assistant.
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
This result must be revalidated against the current worktree.

## 2026-11-21 - Audit and handoff
The project audit identified further review priorities:
Codal retry behavior, response-size limits, date validation,
API error sanitization, technical indicator data sufficiency,
and scheduler shared-state design.

## Persistent engineering principles
- Preserve local changes and untracked files.
- Never commit, push or merge without explicit approval.
- Never use destructive Git commands without explicit approval.
- Missing data is not zero.
- Separate source facts, calculations and AI interpretation.
- Make unsupported capabilities explicit.
- Verify current source and tests before claiming implementation status.
