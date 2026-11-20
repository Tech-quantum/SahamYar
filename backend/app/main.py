from datetime import datetime, timezone
import math
import re

from flask import Flask, jsonify, request

from app.config import settings
from app.analysis.indicators import ema, macd, rsi, sma
from app.errors import ProviderSchemaError, ProviderUnavailable
from app.providers.tsetmc import TsetmcClient
from app.price_service import PriceDataService
from app.price_scheduler import PriceRefreshScheduler

app = Flask(__name__)
tsetmc = TsetmcClient()
price_service = PriceDataService(tsetmc)
price_scheduler = PriceRefreshScheduler(price_service)


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
        return jsonify({"detail": str(exc)}), 502

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
        return jsonify({"detail": str(exc)}), 502

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
        return jsonify({"detail": str(exc)}), 502

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
        return jsonify({"detail": str(exc)}), 502

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
        return jsonify({"detail": str(exc)}), 502

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
        return jsonify({"detail": str(exc)}), 502

    valid_records = []
    for item in history:
        try:
            price = float(item["closing_price"])
            date = int(item["date"])
            if price > 0 and math.isfinite(price):
                valid_records.append((date, price))
        except (KeyError, TypeError, ValueError, OverflowError):
            continue

    valid_records.sort(key=lambda record: record[0])
    dates = [record[0] for record in valid_records]
    prices = [record[1] for record in valid_records]

    macd_result = macd(prices, 12, 26, 9)

    def latest(series):
        return series[-1] if series else None

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
        },
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "analysis_status": "PARTIAL" if prices else "INSUFFICIENT_DATA",
        "recommendation": {
            "action": "INSUFFICIENT_DATA",
            "confidence": None,
            "reason": "برای ارائه پیشنهاد معتبر، داده بنیادی، اقتصادی، سیاسی و بازارهای جهانی نیز لازم است."
        },
        "layers": {
            "stock": {
                "status": "PARTIAL" if prices else "INSUFFICIENT_DATA",
                "technical": {
                    "status": "AVAILABLE" if prices else "INSUFFICIENT_DATA",
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


if __name__ == "__main__":
    price_scheduler.start()
    try:
        app.run(host="127.0.0.1", port=8000, debug=False)
    finally:
        price_scheduler.stop()
