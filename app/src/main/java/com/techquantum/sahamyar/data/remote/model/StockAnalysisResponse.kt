package com.techquantum.sahamyar.data.remote.model

import com.google.gson.JsonElement

data class StockAnalysisResponse(
    val source: String?,
    val ins_code: String?,
    val count: Int,
    val latest_date: Long?,
    val indicators: StockIndicators?,
    val retrieved_at: String?,
    val analysis_status: String? = null,
    val recommendation: AnalysisRecommendation? = null,
    val layers: AnalysisLayers? = null
)

data class StockIndicators(
    val sma: Map<String, Double?>?,
    val ema: Map<String, Double?>?,
    val rsi: Map<String, Double?>?,
    val macd: MacdIndicators?,
    val advanced: AdvancedStockIndicators? = null
)

data class MacdIndicators(
    val line: Double?,
    val signal: Double?,
    val histogram: Double?
)

data class AdvancedStockIndicators(
    val bollinger_bands: Map<String, BollingerBands?>? = null,
    val atr: Map<String, Double?>? = null,
    val stochastic: Map<String, StochasticIndicators?>? = null,
    val obv: Double? = null,
    val volume_sma: Map<String, Double?>? = null,
    val volume_ratio: Map<String, Double?>? = null
)

data class BollingerBands(
    val upper: Double?,
    val middle: Double?,
    val lower: Double?
)

data class StochasticIndicators(
    val k: Double?,
    val d: Double?
)

data class AnalysisRecommendation(
    val action: String? = null,
    val confidence: Double? = null,
    val reason: String? = null
)

data class AnalysisLayers(
    val stock: StockLayer? = null,
    val iran_economy: AnalysisLayer? = null,
    val geopolitical: AnalysisLayer? = null,
    val global_markets: AnalysisLayer? = null
)

data class StockLayer(
    val status: String? = null,
    val technical: AnalysisLayer? = null,
    val fundamental: AnalysisLayer? = null
)

data class AnalysisLayer(
    val status: String? = null,
    val source: String? = null,
    val latest_date: Long? = null,
    val retrieved_at: String? = null,
    val message: String? = null,
    val data: JsonElement? = null
)
