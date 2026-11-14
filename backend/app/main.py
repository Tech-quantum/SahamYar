from datetime import datetime, timezone

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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
