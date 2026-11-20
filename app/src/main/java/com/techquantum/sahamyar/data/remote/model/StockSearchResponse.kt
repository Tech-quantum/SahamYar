package com.techquantum.sahamyar.data.remote.model

data class StockSearchResponse(
    val source: String?,
    val query: String?,
    val count: Int,
    val items: List<StockSearchItem>,
    val retrieved_at: String?
)

data class StockSearchItem(
    val ins_code: String?,
    val symbol: String?,
    val name: String?,
    val isin: String?,
    val market_flow: Int?,
    val market: String?,
    val instrument_type: String? = null,
    val instrument_category: String? = null,
    val instrument_category_label: String? = null
)
