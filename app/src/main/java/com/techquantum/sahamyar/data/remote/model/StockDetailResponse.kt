package com.techquantum.sahamyar.data.remote.model

data class StockDetailResponse(
    val source: String?,
    val ins_code: String?,
    val item: StockDetailItem?,
    val retrieved_at: String?
)

data class StockDetailItem(
    val ins_code: String?,
    val symbol: String?,
    val name: String?,
    val isin: String?,
    val market_flow: Int?,
    val market: String?,
    val sector: String?,
    val eps: Map<String, Any?>?,
    val shares_count: Long?,
    val base_volume: Long?,
    val min_week: Long?,
    val max_week: Long?,
    val min_year: Long?,
    val max_year: Long?,
    val instrument_type: String? = null,
    val instrument_category: String? = null,
    val instrument_category_label: String? = null,
    val average_volume: Long? = null,
    val fundamentals: StockFundamentals? = null
)

data class StockFundamentals(
    val eps_actual: Double? = null,
    val eps_estimated: Double? = null,
    val sector_pe: Double? = null
)

data class StockPriceResponse(
    val source: String?,
    val ins_code: String?,
    val item: StockPriceItem?,
    val retrieved_at: String?
)

data class StockPriceItem(
    val ins_code: String?,
    val date: Long?,
    val closing_price: Long?,
    val last_price: Long?,
    val first_price: Long?,
    val min_price: Long?,
    val max_price: Long?,
    val yesterday_price: Long?,
    val trade_count: Long?,
    val volume: Long?,
    val value: Long?,
    val state: String?
)

data class StockHistoryResponse(
    val source: String?,
    val ins_code: String?,
    val count: Int,
    val items: List<StockHistoryItem>,
    val retrieved_at: String?
)

data class StockHistoryItem(
    val date: Long?,
    val change: Long?,
    val closing_price: Long?,
    val last_price: Long?,
    val first_price: Long?,
    val min_price: Long?,
    val max_price: Long?,
    val yesterday_price: Long?,
    val trade_count: Long?,
    val volume: Long?,
    val value: Long?
)
