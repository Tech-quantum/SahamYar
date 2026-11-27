package com.techquantum.sahamyar.data.remote.api

import com.techquantum.sahamyar.data.analysis.AdvancedTechnicalIndicators
import com.techquantum.sahamyar.data.analysis.TechnicalIndicatorCalculator
import com.techquantum.sahamyar.data.remote.model.*
import java.time.Instant

object TsetmcAnalysisMapper {

    fun analyze(
        history: StockHistoryResponse,
        count: Int
    ): StockAnalysisResponse {
        require(count in 1..365)

        val records = history.items.takeLast(count)
        val validCloseCount = records.count { validClose(it) }

        // Close-based indicators must not bridge gaps in the source history.
        val closeRecords = records.asReversed()
            .takeWhile { validClose(it) }
            .asReversed()

        val closes = closeRecords.mapNotNull {
            it.closing_price?.toDouble()?.takeIf { value ->
                value.isFinite() && value > 0.0
            }
        }

        val sma20 = TechnicalIndicatorCalculator.sma(closes, 20).lastOrNull()
        val sma50 = TechnicalIndicatorCalculator.sma(closes, 50).lastOrNull()
        val sma200 = TechnicalIndicatorCalculator.sma(closes, 200).lastOrNull()
        val ema12 = TechnicalIndicatorCalculator.ema(closes, 12).lastOrNull()
        val ema26 = TechnicalIndicatorCalculator.ema(closes, 26).lastOrNull()
        val rsi14 = TechnicalIndicatorCalculator.rsi(closes, 14).lastOrNull()
        val macd = TechnicalIndicatorCalculator.macd(closes)

        val bollingerPrices = records.asReversed()
            .takeWhile { validClose(it) }
            .asReversed()
            .mapNotNull { it.closing_price?.toDouble() }

        val bands = AdvancedTechnicalIndicators.bollinger(bollingerPrices)
        val bollinger = BollingerBands(
            upper = bands.upper.lastOrNull(),
            middle = bands.middle.lastOrNull(),
            lower = bands.lower.lastOrNull()
        )

        val ohlc = records.asReversed()
            .takeWhile { validOhlc(it) }
            .asReversed()

        val highs = ohlc.mapNotNull { it.max_price?.toDouble() }
        val lows = ohlc.mapNotNull { it.min_price?.toDouble() }
        val ohlcCloses = ohlc.mapNotNull { it.closing_price?.toDouble() }

        val atr14 = AdvancedTechnicalIndicators.atr(
            highs, lows, ohlcCloses, 14
        ).lastOrNull()

        val stochastic = AdvancedTechnicalIndicators.stochastic(
            highs, lows, ohlcCloses, 14, 3
        )

        val volumeRecords = records.asReversed()
            .takeWhile { validVolumeRecord(it) }
            .asReversed()

        val volumeCloses = volumeRecords.mapNotNull {
            it.closing_price?.toDouble()
        }
        val volumes = volumeRecords.mapNotNull {
            it.volume?.toDouble()
        }

        val obv = AdvancedTechnicalIndicators.obv(
            volumeCloses, volumes
        ).lastOrNull()

        val volumeSma20 = AdvancedTechnicalIndicators.volumeSma(
            volumes, 20
        ).lastOrNull()

        val volumeRatio20 = AdvancedTechnicalIndicators.volumeRatio(
            volumes, 20
        ).lastOrNull()

        val indicators = StockIndicators(
            sma = mapOf(
                "20" to sma20,
                "50" to sma50,
                "200" to sma200
            ),
            ema = mapOf(
                "12" to ema12,
                "26" to ema26
            ),
            rsi = mapOf("14" to rsi14),
            macd = MacdIndicators(
                line = macd.line.lastOrNull(),
                signal = macd.signal.lastOrNull(),
                histogram = macd.histogram.lastOrNull()
            ),
            advanced = AdvancedStockIndicators(
                bollinger_bands = mapOf("20" to bollinger),
                atr = mapOf("14" to atr14),
                stochastic = mapOf(
                    "14" to StochasticIndicators(
                        k = stochastic.k.lastOrNull(),
                        d = stochastic.d.lastOrNull()
                    )
                ),
                obv = obv,
                volume_sma = mapOf("20" to volumeSma20),
                volume_ratio = mapOf("20" to volumeRatio20)
            )
        )

        val available = listOfNotNull(
            sma20, sma50, sma200, ema12, ema26, rsi14,
            macd.line.lastOrNull(),
            macd.signal.lastOrNull(),
            macd.histogram.lastOrNull(),
            bands.upper.lastOrNull(),
            atr14,
            stochastic.k.lastOrNull(),
            stochastic.d.lastOrNull(),
            obv,
            volumeSma20,
            volumeRatio20
        ).isNotEmpty()

        val status = if (available) "PARTIAL" else "INSUFFICIENT_DATA"
        val retrievedAt = Instant.now().toString()
        // Match the backend contract: count and latest_date describe
        // records that contain a valid closing price.
        val latestValidRecord = records.lastOrNull { validClose(it) }
        val latestDate = latestValidRecord?.date

        return StockAnalysisResponse(
            source = "TSETMC",
            ins_code = history.ins_code,
            count = validCloseCount,
            latest_date = latestDate,
            indicators = indicators,
            retrieved_at = retrievedAt,
            analysis_status = status,
            recommendation = AnalysisRecommendation(
                action = "INSUFFICIENT_DATA",
                reason = "برای پیشنهاد خرید یا فروش، داده‌های بنیادی و سایر لایه‌های تحلیلی کافی نیست."
            ),
            layers = AnalysisLayers(
                stock = StockLayer(
                    status = status,
                    technical = AnalysisLayer(
                        status = if (available) "AVAILABLE" else "INSUFFICIENT_DATA",
                        source = "TSETMC",
                        latest_date = latestDate,
                        retrieved_at = retrievedAt
                    ),
                    fundamental = AnalysisLayer(
                        status = "UNAVAILABLE",
                        source = "TSETMC",
                        retrieved_at = retrievedAt,
                        message = "داده‌های بنیادی هنوز برای تحلیل کامل آماده نیستند."
                    )
                ),
                iran_economy = AnalysisLayer(status = "UNAVAILABLE"),
                geopolitical = AnalysisLayer(status = "UNAVAILABLE"),
                global_markets = AnalysisLayer(status = "UNAVAILABLE")
            )
        )
    }

    private fun validClose(item: StockHistoryItem): Boolean =
        item.closing_price?.let { it > 0L } == true

    private fun validOhlc(item: StockHistoryItem): Boolean {
        val close = item.closing_price ?: return false
        val high = item.max_price ?: return false
        val low = item.min_price ?: return false

        return close > 0L &&
            high > 0L &&
            low > 0L &&
            high >= low &&
            close in low..high
    }

    private fun validVolumeRecord(item: StockHistoryItem): Boolean =
        validClose(item) && (item.volume?.let { it >= 0L } == true)
}
