import logging
from datetime import datetime, timezone
import math
import re
from pathlib import Path

from flask import Flask, jsonify, request

from app.config import settings
from app.analysis.indicators import ema, macd, rsi, sma
from app.analysis.advanced_indicators import (
    atr, bollinger_bands, obv, stochastic, volume_ratio, volume_sma,
)
from app.errors import ProviderSchemaError, ProviderUnavailable
from app.providers.tsetmc import TsetmcClient
from app.market_calendar import (
    CalendarDataError,
    MarketCalendar,
    current_jalali_year,
    load_market_events,
)
from app.market_hours import MarketHours, TEHRAN
from app.price_service import PriceDataService
from app.price_scheduler import PriceRefreshScheduler
from app.providers.codal_client import CodalClient
from app.services.financial_service import CodalFinancialService

app = Flask(__name__)
tsetmc = TsetmcClient()


def _load_market_hours():
    jalali_year = current_jalali_year()
    calendars_dir = (
        Path(__file__).resolve().parent / "data" / "calendars"
    )
    calendar_path = calendars_dir / f"{jalali_year}.json"
    events_path = calendars_dir / "market_events.json"

    try:
        events = load_market_events(events_path)
        calendar = MarketCalendar.from_json(calendar_path, events=events)
        if calendar.jalali_year != jalali_year:
            raise CalendarDataError(
                "Calendar file does not match the current Jalali year."
            )
        return MarketHours(calendar=calendar, require_calendar=True)
    except CalendarDataError:
        logging.getLogger(__name__).exception(
            "Market calendar unavailable; price refresh will fail closed."
        )
        return MarketHours(
            require_calendar=True,
            calendar_error="Current-year market calendar is unavailable.",
        )


market_hours = _load_market_hours()
price_service = PriceDataService(tsetmc, market_hours=market_hours)
price_scheduler = PriceRefreshScheduler(price_service)
codal_client = CodalClient()
financial_service = CodalFinancialService(codal_client)

logger = logging.getLogger(__name__)


def _provider_error_response(exc, *, data_status=None):
    """Log upstream details while returning a sanitized API response."""
    logger.exception("Upstream provider request failed")

    if isinstance(exc, ProviderSchemaError):
        detail = "Upstream provider returned an invalid response."
    else:
        detail = "Upstream data provider is temporarily unavailable."

    payload = {"detail": detail}
    if data_status is not None:
        payload["data_status"] = data_status

    return jsonify(payload), 502




def _serialize_calendar_holiday(item):
    return {
        "date": item.day.isoformat(),
        "name": item.name,
        "source": item.source,
        "source_url": item.source_url,
    }


def _serialize_calendar_event(item):
    return {
        "event_id": item.event_id,
        "title": item.title,
        "issuer": item.issuer,
        "source_url": item.source_url,
        "published_at": item.published_at.isoformat(),
        "effective_from": item.effective_from.isoformat(),
        "effective_to": item.effective_to.isoformat(),
        "scope": {
            "level": item.scope.level,
            "market": item.scope.market,
            "symbol": item.scope.symbol,
            "operation": item.scope.operation,
        },
        "status": item.status,
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
    }


@app.get("/api/v1/market/status")
def get_market_status():
    now = datetime.now(TEHRAN)
    status = market_hours.get_status(now)
    calendar = market_hours.calendar
    calendar_status = status.calendar_status
    calendar_day = None

    calendar_available = (
        calendar is not None
        and calendar_status not in {"needs_update", "invalid"}
    )

    if calendar is None and calendar_status is None:
        calendar_status = "unavailable"

    if calendar_available:
        try:
            # Without scope arguments, only all-market events are included.
            calendar_day = calendar.get_status(now.date(), now=now)
        except Exception:
            logger.exception("Unable to build market calendar API response")
            calendar_available = False
            calendar_status = "invalid"

    if not calendar_available and calendar_status not in {
        "needs_update", "invalid", "unavailable"
    }:
        calendar_status = "unavailable"

    trading_day_status = (
        "unknown" if not calendar_available
        else "trading_day" if status.is_trading_day
        else "non_trading_day"
    )
    market_state = (
        "unknown" if not calendar_available
        else "open" if status.phase != "closed"
        else "closed"
    )

    return jsonify({
        "market": {
            "status": market_state,
            "phase": status.phase,
            "is_trading_day": status.is_trading_day,
            "trading_day_status": trading_day_status,
            "local_date": now.date().isoformat(),
            "local_time": status.local_time,
            "timezone": "Asia/Tehran",
        },
        "calendar": {
            "available": calendar_available,
            "status": calendar_status or "unknown",
            "calendar_year": calendar.calendar_year if calendar else None,
            "jalali_year": calendar.jalali_year if calendar else None,
            "source": calendar.source if calendar else None,
            "source_url": calendar.source_url if calendar else None,
            "updated_at": (
                calendar.updated_at.isoformat()
                if calendar and calendar.updated_at else None
            ),
            "holidays": (
                [
                    _serialize_calendar_holiday(x)
                    for x in sorted(calendar.holidays, key=lambda item: item.day)
                ]
                if calendar_available and calendar else []
            ),
            "today_holidays": (
                [_serialize_calendar_holiday(x) for x in calendar_day.holidays]
                if calendar_day else []
            ),
            "closure_events": (
                [_serialize_calendar_event(x) for x in calendar_day.closure_events]
                if calendar_day else []
            ),
            "warnings": (
                [_serialize_calendar_event(x) for x in calendar_day.warnings]
                if calendar_day else []
            ),
        },
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    })


def _scoped_market_calendar_response(*, level, market, symbol=None):
    now = datetime.now(TEHRAN)
    calendar = market_hours.calendar
    market_status = market_hours.get_status(now)
    calendar_status = market_status.calendar_status
    calendar_day = None

    calendar_available = (
        calendar is not None
        and calendar_status not in {"needs_update", "invalid"}
    )

    if calendar is None and calendar_status is None:
        calendar_status = "unavailable"

    if calendar_available:
        try:
            calendar_day = calendar.get_status(
                now.date(),
                market=market,
                symbol=symbol,
                now=now,
            )
        except Exception:
            logger.exception("Unable to build scoped market calendar response")
            calendar_available = False
            calendar_status = "invalid"

    if not calendar_available and calendar_status not in {
        "needs_update", "invalid", "unavailable"
    }:
        calendar_status = "unavailable"

    return jsonify({
        "scope": {
            "level": level,
            "market": market,
            "symbol": symbol,
        },
        "calendar": {
            "available": calendar_available,
            "status": (
                calendar_day.status
                if calendar_day is not None
                else "unknown"
            ),
            "is_closed": (
                calendar_day.is_closed
                if calendar_day is not None
                else None
            ),
            "is_official_holiday": (
                calendar_day.is_official_holiday
                if calendar_day is not None
                else None
            ),
            "calendar_status": calendar_status or "unknown",
            "calendar_year": calendar.calendar_year if calendar else None,
            "jalali_year": calendar.jalali_year if calendar else None,
            "source": calendar.source if calendar else None,
            "source_url": calendar.source_url if calendar else None,
            "updated_at": (
                calendar.updated_at.isoformat()
                if calendar and calendar.updated_at else None
            ),
            "today_holidays": (
                [_serialize_calendar_holiday(x) for x in calendar_day.holidays]
                if calendar_day else []
            ),
            "closure_events": (
                [_serialize_calendar_event(x) for x in calendar_day.closure_events]
                if calendar_day else []
            ),
            "warnings": (
                [_serialize_calendar_event(x) for x in calendar_day.warnings]
                if calendar_day else []
            ),
        },
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    })


@app.get("/api/v1/markets/<market>/status")
def get_scoped_market_status(market):
    if not market.strip() or len(market) > 128:
        return jsonify({"detail": "Invalid market identifier."}), 400

    return _scoped_market_calendar_response(
        level="market",
        market=market,
    )


@app.get("/api/v1/stocks/<ins_code>/market-status")
def get_stock_market_status(ins_code):
    if not re.fullmatch(r"[0-9]{5,30}", ins_code):
        return jsonify({
            "detail": "Instrument code must contain 5 to 30 digits."
        }), 400

    try:
        item = tsetmc.get_instrument_info(ins_code)
        if not isinstance(item, dict):
            raise ProviderSchemaError("Invalid instrument response.")

        symbol = item.get("symbol")
        market = item.get("market")
        if (
            not isinstance(symbol, str) or not symbol.strip()
            or not isinstance(market, str) or not market.strip()
        ):
            raise ProviderSchemaError(
                "Instrument response is missing symbol or market."
            )
    except (ProviderUnavailable, ProviderSchemaError) as exc:
        return _provider_error_response(exc)

    return _scoped_market_calendar_response(
        level="symbol",
        market=market,
        symbol=symbol,
    )


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": settings.app_name,
    })


@app.get("/api/v1/stocks/search")
def search_stocks():
    query = request.args.get("q", "").strip()

    if not 2 <= len(query) <= 80:
        return jsonify({
            "detail": "Query length must be between 2 and 80 characters."
        }), 400

    try:
        items = tsetmc.search_instruments(query)
    except (ProviderUnavailable, ProviderSchemaError) as exc:
        return _provider_error_response(exc)

    return jsonify({
        "source": "TSETMC",
        "query": query,
        "count": len(items),
        "items": items,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    })


@app.get("/api/v1/stocks/<ins_code>")
def get_stock_info(ins_code):
    if not re.fullmatch(r"[0-9]{5,30}", ins_code):
        return jsonify({
            "detail": "Instrument code must contain 5 to 30 digits."
        }), 400

    try:
        item = tsetmc.get_instrument_info(ins_code)
    except (ProviderUnavailable, ProviderSchemaError) as exc:
        return _provider_error_response(exc)

    return jsonify({
        "source": "TSETMC",
        "ins_code": ins_code,
        "item": item,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    })


@app.get("/api/v1/stocks/<ins_code>/prices")
def get_stock_prices(ins_code):
    if not re.fullmatch(r"[0-9]{5,30}", ins_code):
        return jsonify({
            "detail": "Instrument code must contain 5 to 30 digits."
        }), 400

    try:
        result = price_service.get_price(ins_code)
    except (ProviderUnavailable, ProviderSchemaError) as exc:
        return _provider_error_response(exc)

    return jsonify(result)


@app.get("/api/v1/stocks/<ins_code>/history")
def get_stock_history(ins_code):
    if not re.fullmatch(r"[0-9]{5,30}", ins_code):
        return jsonify({
            "detail": "Instrument code must contain 5 to 30 digits."
        }), 400

    raw_count = request.args.get("count", "30")
    if not raw_count.isdigit() or not 1 <= int(raw_count) <= 365:
        return jsonify({
            "detail": "Count must be an integer between 1 and 365."
        }), 400

    count = int(raw_count)

    try:
        items = tsetmc.get_daily_prices(ins_code, count)
    except (ProviderUnavailable, ProviderSchemaError) as exc:
        return _provider_error_response(exc)

    return jsonify({
        "source": "TSETMC",
        "ins_code": ins_code,
        "count": len(items),
        "items": items,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    })






@app.get("/api/v1/stocks/<ins_code>/analysis")
def get_stock_analysis(ins_code):
    if not re.fullmatch(r"[0-9]{5,30}", ins_code):
        return jsonify({"detail": "Invalid instrument code."}), 400

    raw_count = request.args.get("count", "365")
    if not raw_count.isdigit() or not 1 <= int(raw_count) <= 365:
        return jsonify({"detail": "Count must be between 1 and 365."}), 400

    count = int(raw_count)

    try:
        instrument = tsetmc.get_instrument_info(ins_code)
    except (ProviderUnavailable, ProviderSchemaError) as exc:
        return _provider_error_response(exc)

    category = instrument.get("instrument_category")
    if category not in {"COMMON_STOCK", "RIGHTS"}:
        label = instrument.get("instrument_category_label") or "سایر"
        return jsonify({
            "source": "TSETMC",
            "ins_code": ins_code,
            "count": 0,
            "latest_date": None,
            "indicators": None,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "analysis_status": "NOT_SUPPORTED",
            "recommendation": {
                "action": "NOT_SUPPORTED",
                "confidence": None,
                "reason": (
                    f"تحلیل تکنیکال فعلی برای ابزار «{label}» پشتیبانی نمی‌شود؛ "
                    "بنابراین شاخص یا پیشنهاد سهام‌محور ارائه نشد."
                ),
            },
            "layers": {
                "stock": {
                    "status": "NOT_SUPPORTED",
                    "technical": {
                        "status": "NOT_SUPPORTED",
                        "source": None,
                        "latest_date": None,
                        "message": "تحلیل تکنیکال سهام برای این ابزار پشتیبانی نمی‌شود.",
                    },
                    "fundamental": {
                        "status": "UNAVAILABLE",
                        "source": None,
                        "retrieved_at": None,
                        "data": None,
                        "message": "منبع معتبر داده‌های بنیادی هنوز متصل نشده است.",
                    },
                },
                "iran_economy": {
                    "status": "UNAVAILABLE", "source": None,
                    "retrieved_at": None, "data": None,
                    "message": "منابع معتبر داده‌های اقتصاد ایران هنوز متصل نشده‌اند.",
                },
                "geopolitical": {
                    "status": "UNAVAILABLE", "source": None,
                    "retrieved_at": None, "data": None,
                    "message": "منابع معتبر اخبار و ریسک‌های سیاسی هنوز متصل نشده‌اند.",
                },
                "global_markets": {
                    "status": "UNAVAILABLE", "source": None,
                    "retrieved_at": None, "data": None,
                    "message": "منابع معتبر بازارهای جهانی هنوز متصل نشده‌اند.",
                },
            },
        })

    try:
        history = tsetmc.get_daily_prices(ins_code, count)
    except (ProviderUnavailable, ProviderSchemaError) as exc:
        return _provider_error_response(exc)

    valid_records = []
    bollinger_history = []
    advanced_history = []

    for item in history:
        try:
            record_date = int(item["date"])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue

        try:
            price = float(item["closing_price"])
        except (KeyError, TypeError, ValueError, OverflowError):
            bollinger_history.append((record_date, None))
            advanced_history.append((record_date, None, item))
            continue

        if price > 0 and math.isfinite(price):
            valid_records.append((record_date, price, item))
            bollinger_history.append((record_date, price))
            advanced_history.append((record_date, price, item))
        else:
            bollinger_history.append((record_date, None))
            advanced_history.append((record_date, None, item))

    valid_records.sort(key=lambda record: record[0])
    bollinger_history.sort(key=lambda record: record[0])
    dates = [record[0] for record in valid_records]
    prices = [record[1] for record in valid_records]

    macd_result = macd(prices, 12, 26, 9)

    def latest(series):
        return series[-1] if series else None

    def valid_number(value, *, positive=False, non_negative=False):
        if isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(number):
            return None
        if positive and number <= 0:
            return None
        if non_negative and number < 0:
            return None
        return number

    # Use only the latest contiguous suffix of valid OHLC candles.
    # This prevents indicators from bridging missing or malformed candles.
    advanced_history.sort(key=lambda record: record[0])

    ohlc_records = []
    for _, close, item in reversed(advanced_history):
        if close is None:
            break

        high = valid_number(item.get("max_price"), positive=True)
        low = valid_number(item.get("min_price"), positive=True)

        if high is None or low is None or high < low:
            break
        if not low <= close <= high:
            break

        ohlc_records.append((high, low, close))

    ohlc_records.reverse()
    highs = [record[0] for record in ohlc_records]
    lows = [record[1] for record in ohlc_records]
    ohlc_closes = [record[2] for record in ohlc_records]

    # Volume-based indicators use their own contiguous valid suffix.
    close_volume_records = []
    for _, close, item in reversed(advanced_history):
        if close is None:
            break

        volume = valid_number(item.get("volume"), non_negative=True)
        if volume is None:
            break
        close_volume_records.append((close, volume))

    close_volume_records.reverse()
    volume_closes = [record[0] for record in close_volume_records]
    volumes = [record[1] for record in close_volume_records]

    # Bollinger Bands use the latest contiguous valid closing-price suffix.
    # Invalid observations break the suffix instead of being silently skipped.
    bollinger_prices = []
    for _, price in reversed(bollinger_history):
        if price is None:
            break
        bollinger_prices.append(price)

    bollinger_prices.reverse()
    bands = bollinger_bands(bollinger_prices, 20, 2.0)
    atr_result = atr(highs, lows, ohlc_closes, 14)
    stochastic_result = stochastic(highs, lows, ohlc_closes, 14, 3)
    obv_result = obv(volume_closes, volumes)
    volume_sma_result = volume_sma(volumes, 20)
    volume_ratio_result = volume_ratio(volumes, 20)

    # A technical layer is available only when at least one indicator
    # has an actual computed value, not merely because prices exist.
    technical_values = [
        latest(sma(prices, 20)),
        latest(sma(prices, 50)),
        latest(sma(prices, 200)),
        latest(ema(prices, 12)),
        latest(ema(prices, 26)),
        latest(rsi(prices, 14)),
        latest(macd_result["macd"]),
        latest(macd_result["signal"]),
        latest(macd_result["histogram"]),
        latest(bands["upper"]),
        latest(bands["middle"]),
        latest(bands["lower"]),
        latest(atr_result),
        latest(stochastic_result["k"]),
        latest(stochastic_result["d"]),
        latest(obv_result),
        latest(volume_sma_result),
        latest(volume_ratio_result),
    ]
    has_technical_data = any(value is not None for value in technical_values)

    return jsonify({
        "source": "TSETMC",
        "ins_code": ins_code,
        "count": len(prices),
        "latest_date": dates[-1] if dates else None,
        "indicators": {
            "sma": {
                "20": latest(sma(prices, 20)),
                "50": latest(sma(prices, 50)),
                "200": latest(sma(prices, 200)),
            },
            "ema": {
                "12": latest(ema(prices, 12)),
                "26": latest(ema(prices, 26)),
            },
            "rsi": {"14": latest(rsi(prices, 14))},
            "macd": {
                "line": latest(macd_result["macd"]),
                "signal": latest(macd_result["signal"]),
                "histogram": latest(macd_result["histogram"]),
            },
            "advanced": {
                "bollinger_bands": {
                    "20": {
                        "upper": latest(bands["upper"]),
                        "middle": latest(bands["middle"]),
                        "lower": latest(bands["lower"]),
                    },
                },
                "atr": {"14": latest(atr_result)},
                "stochastic": {
                    "14": {
                        "k": latest(stochastic_result["k"]),
                        "d": latest(stochastic_result["d"]),
                    },
                },
                "obv": latest(obv_result),
                "volume_sma": {"20": latest(volume_sma_result)},
                "volume_ratio": {"20": latest(volume_ratio_result)},
            },
        },
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "analysis_status": "PARTIAL" if has_technical_data else "INSUFFICIENT_DATA",
        "recommendation": {
            "action": "INSUFFICIENT_DATA",
            "confidence": None,
            "reason": "برای ارائه پیشنهاد معتبر، داده بنیادی، اقتصادی، سیاسی و بازارهای جهانی نیز لازم است."
        },
        "layers": {
            "stock": {
                "status": "PARTIAL" if has_technical_data else "INSUFFICIENT_DATA",
                "technical": {
                    "status": "AVAILABLE" if has_technical_data else "INSUFFICIENT_DATA",
                    "source": "TSETMC",
                    "latest_date": dates[-1] if dates else None,
                },
                "fundamental": {
                    "status": "UNAVAILABLE",
                    "source": None,
                    "retrieved_at": None,
                    "data": None,
                    "message": "منبع معتبر داده‌های بنیادی هنوز متصل نشده است."
                }
            },
            "iran_economy": {
                "status": "UNAVAILABLE",
                "source": None,
                "retrieved_at": None,
                "data": None,
                "message": "منابع معتبر داده‌های اقتصاد ایران هنوز متصل نشده‌اند."
            },
            "geopolitical": {
                "status": "UNAVAILABLE",
                "source": None,
                "retrieved_at": None,
                "data": None,
                "message": "منابع معتبر اخبار و ریسک‌های سیاسی هنوز متصل نشده‌اند."
            },
            "global_markets": {
                "status": "UNAVAILABLE",
                "source": None,
                "retrieved_at": None,
                "data": None,
                "message": "منابع معتبر بازارهای جهانی هنوز متصل نشده‌اند."
            }
        }
    })


def _codal_symbol_for_instrument(ins_code):
    instrument = tsetmc.get_instrument_info(ins_code)
    symbol = instrument.get("symbol") if isinstance(instrument, dict) else None

    if not isinstance(symbol, str) or not symbol.strip():
        raise ProviderSchemaError(
            "TSETMC did not provide a symbol for Codal lookup."
        )

    return symbol.strip()


@app.get("/api/v1/stocks/<ins_code>/financial-reports")
def search_financial_reports(ins_code):
    if not re.fullmatch(r"[0-9]{5,30}", ins_code):
        return jsonify({"detail": "Invalid instrument code."}), 400

    raw_page = request.args.get("page", "1")
    if not raw_page.isdigit() or not 1 <= int(raw_page) <= 1000:
        return jsonify({
            "detail": "Page must be between 1 and 1000."
        }), 400

    try:
        symbol = _codal_symbol_for_instrument(ins_code)
        result = financial_service.search_reports(
            symbol,
            page=int(raw_page),
        )
    except (ProviderUnavailable, ProviderSchemaError) as exc:
        return _provider_error_response(exc, data_status="unavailable")

    return jsonify({
        **result,
        "ins_code": ins_code,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "data_status": "available" if result["items"] else "empty",
    })


@app.get(
    "/api/v1/stocks/<ins_code>/financial-reports/<tracing_no>"
)
def get_financial_report(ins_code, tracing_no):
    if not re.fullmatch(r"[0-9]{5,30}", ins_code):
        return jsonify({"detail": "Invalid instrument code."}), 400

    if not tracing_no.isdigit() or len(tracing_no) > 30:
        return jsonify({"detail": "Invalid Codal tracing number."}), 400

    raw_page = request.args.get("page", "1")
    if not raw_page.isdigit() or not 1 <= int(raw_page) <= 1000:
        return jsonify({
            "detail": "Page must be between 1 and 1000."
        }), 400

    try:
        symbol = _codal_symbol_for_instrument(ins_code)
        result = financial_service.get_financial_report(
            symbol,
            tracing_no,
            page=int(raw_page),
        )
    except LookupError:
        return jsonify({
            "detail": "The requested financial report was not found.",
            "data_status": "not_found",
        }), 404
    except (ProviderUnavailable, ProviderSchemaError) as exc:
        return _provider_error_response(exc, data_status="unavailable")

    return jsonify({
        **result,
        "ins_code": ins_code,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    })


if __name__ == "__main__":
    price_scheduler.start()
    try:
        app.run(host="127.0.0.1", port=8000, debug=False)
    finally:
        price_scheduler.stop()
