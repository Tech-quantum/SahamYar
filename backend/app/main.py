from datetime import datetime, timezone
import re

from flask import Flask, jsonify, request

from app.config import settings
from app.errors import ProviderSchemaError, ProviderUnavailable
from app.providers.tsetmc import TsetmcClient

app = Flask(__name__)
tsetmc = TsetmcClient()


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
        item = tsetmc.get_closing_price_info(ins_code)
    except (ProviderUnavailable, ProviderSchemaError) as exc:
        return jsonify({"detail": str(exc)}), 502

    return jsonify({
        "source": "TSETMC",
        "ins_code": ins_code,
        "item": item,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    })


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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
