package com.techquantum.sahamyar.data.remote.api

import com.google.gson.JsonArray
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import com.techquantum.sahamyar.data.remote.model.*
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.format.ResolverStyle
import java.time.Instant

object TsetmcStockMapper {

    private fun JsonObject.obj(key: String) =
        get(key)?.takeIf { it.isJsonObject }?.asJsonObject

    private fun JsonObject.str(key: String): String? {
        val value = get(key) ?: return null
        if (value.isJsonNull || !value.isJsonPrimitive) return null
        val primitive = value.asJsonPrimitive
        if (!primitive.isString && !primitive.isNumber) return null
        return runCatching { primitive.asString }.getOrNull()
    }

    private fun JsonObject.double(key: String): Double? =
        get(key).numberOrNull()

    private fun JsonObject.long(key: String): Long? =
        get(key).longOrNull()

    private fun JsonElement?.numberOrNull(): Double? {
        if (this == null || isJsonNull || !isJsonPrimitive) return null
        val p = asJsonPrimitive
        if (!p.isNumber && !p.isString) return null
        return runCatching { p.asString.toDouble() }
            .getOrNull()?.takeIf { it.isFinite() }
    }

    private fun JsonElement?.longOrNull(): Long? {
        if (this == null || isJsonNull || !isJsonPrimitive) return null
        val p = asJsonPrimitive
        if (!p.isNumber && !p.isString) return null
        return runCatching {
            p.asString.toBigDecimal().longValueExact()
        }.getOrNull()
    }

    private fun validDate(value: Long?): Long? {
        if (value == null) return null
        val text = value.toString()
        if (!text.matches(Regex("\\d{8}"))) return null
        return runCatching {
            LocalDate.parse(
                text,
                DateTimeFormatter.ofPattern("uuuuMMdd")
                    .withResolverStyle(ResolverStyle.STRICT)
            )
            value
        }.getOrNull()
    }

    fun detail(insCode: String, raw: JsonObject): StockDetailResponse {
        val epsObject = raw.obj("eps")
        val sectorObject = raw.obj("sector")

        val symbol = raw.str("lVal18AFC")
        val name = raw.str("lVal30").orEmpty()
        val type = raw.str("cgrValCot")?.uppercase()
        val (category, categoryLabel) =
            TsetmcInstrumentClassifier.classify(name, type)

        val actualEps = epsObject?.double("epsValue")
        val estimatedEps = epsObject?.double("estimatedEPS")
        val sectorPe = epsObject?.double("sectorPE")

        val epsMap = epsObject?.let {
            mapOf(
                "epsValue" to actualEps,
                "estimatedEPS" to estimatedEps,
                "sectorPE" to sectorPe
            )
        }

        val item = StockDetailItem(
            ins_code = raw.str("insCode") ?: insCode,
            symbol = symbol,
            name = name,
            isin = raw.str("cIsin"),
            market_flow = raw.str("flow")?.toIntOrNull(),
            market = raw.str("flowTitle"),
            sector = sectorObject?.str("lSecVal"),
            eps = epsMap,
            shares_count = raw.long("zTitad"),
            base_volume = raw.long("baseVol"),
            min_week = raw.long("minWeek"),
            max_week = raw.long("maxWeek"),
            min_year = raw.long("minYear"),
            max_year = raw.long("maxYear"),
            instrument_type = type,
            instrument_category = category,
            instrument_category_label = categoryLabel,
            average_volume = raw.long("qTotTran5JAvg"),
            fundamentals = StockFundamentals(
                eps_actual = actualEps,
                eps_estimated = estimatedEps,
                sector_pe = sectorPe
            )
        )

        return StockDetailResponse(
            source = "TSETMC",
            ins_code = insCode,
            item = item,
            retrieved_at = Instant.now().toString()
        )
    }

    fun price(insCode: String, raw: JsonObject): StockPriceResponse {
        val state = raw.obj("instrumentState")?.str("cEtavalTitle")

        val item = StockPriceItem(
            ins_code = insCode,
            date = validDate(raw.long("finalLastDate")),
            closing_price = raw.long("pClosing"),
            last_price = raw.long("pDrCotVal"),
            first_price = raw.long("priceFirst"),
            min_price = raw.long("priceMin"),
            max_price = raw.long("priceMax"),
            yesterday_price = raw.long("priceYesterday"),
            trade_count = raw.long("zTotTran"),
            volume = raw.long("qTotTran5J"),
            value = raw.long("qTotCap"),
            state = state
        )

        return StockPriceResponse(
            source = "TSETMC",
            ins_code = insCode,
            item = item,
            retrieved_at = Instant.now().toString()
        )
    }

    private fun mergeHistoryRows(rows: List<StockHistoryItem>): StockHistoryItem? {
        if (rows.isEmpty()) return null

        var conflict = false

        fun mergeValue(selector: (StockHistoryItem) -> Long?): Long? {
            val values = rows.mapNotNull(selector).distinct()
            if (values.size > 1) {
                conflict = true
                return null
            }
            return values.singleOrNull()
        }

        val first = rows.first()
        val merged = first.copy(
            change = mergeValue { it.change },
            closing_price = mergeValue { it.closing_price },
            last_price = mergeValue { it.last_price },
            first_price = mergeValue { it.first_price },
            min_price = mergeValue { it.min_price },
            max_price = mergeValue { it.max_price },
            yesterday_price = mergeValue { it.yesterday_price },
            trade_count = mergeValue { it.trade_count },
            volume = mergeValue { it.volume },
            value = mergeValue { it.value }
        )

        return merged.takeUnless { conflict }
    }

    fun history(
        insCode: String,
        raw: JsonObject,
        count: Int
    ): StockHistoryResponse {
        require(count in 1..365)

        val rows: JsonArray = raw.getAsJsonArray("closingPriceDaily")
            ?: throw IllegalStateException("ساختار تاریخچه TSETMC معتبر نیست.")

        val items = rows.mapNotNull { element ->
            if (!element.isJsonObject) return@mapNotNull null
            val row = element.asJsonObject
            val date = validDate(row.long("dEven"))
                ?: return@mapNotNull null

            StockHistoryItem(
                date = date,
                change = row.long("priceChange"),
                closing_price = row.long("pClosing"),
                last_price = row.long("pDrCotVal"),
                first_price = row.long("priceFirst"),
                min_price = row.long("priceMin"),
                max_price = row.long("priceMax"),
                yesterday_price = row.long("priceYesterday"),
                trade_count = row.long("zTotTran"),
                volume = row.long("qTotTran5J"),
                value = row.long("qTotCap")
            )
        }
            .groupBy { it.date }
            .values
            .mapNotNull(::mergeHistoryRows)
            .sortedBy { it.date }
            .takeLast(count)

        return StockHistoryResponse(
            source = "TSETMC",
            ins_code = insCode,
            count = items.size,
            items = items,
            retrieved_at = Instant.now().toString()
        )
    }
}
