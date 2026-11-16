package com.techquantum.sahamyar.data.remote.model

data class StockAnalysisResponse(
    val source: String?,
    val ins_code: String?,
    val count: Int,
    val latest_date: Long?,
    val indicators: StockIndicators?,
    val retrieved_at: String?
)

data class StockIndicators(
    val sma: Map<String, Double?>?,
    val ema: Map<String, Double?>?,
    val rsi: Map<String, Double?>?,
    val macd: MacdIndicators?
)

data class MacdIndicators(
    val line: Double?,
    val signal: Double?,
    val histogram: Double?
)
