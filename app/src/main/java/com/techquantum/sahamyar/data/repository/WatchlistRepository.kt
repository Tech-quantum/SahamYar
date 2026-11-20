package com.techquantum.sahamyar.data.repository

import com.techquantum.sahamyar.data.local.dao.WatchlistDao
import com.techquantum.sahamyar.data.local.entity.WatchlistEntity

class WatchlistRepository(
    private val dao: WatchlistDao
) {
    fun observeItems() = dao.observeItems()

    suspend fun addStock(
        insCode: String,
        symbol: String,
        companyName: String?,
        market: String?
    ): Long {
        require(insCode.isNotBlank()) { "کد ابزار معتبر نیست." }
        require(symbol.isNotBlank()) { "نماد معتبر نیست." }

        return dao.insert(
            WatchlistEntity(
                insCode = insCode,
                symbol = symbol,
                companyName = companyName,
                market = market
            )
        )
    }

    suspend fun removeStock(id: Long): Boolean {
        return dao.deleteById(id) > 0
    }

    suspend fun isTracked(insCode: String): Boolean {
        return dao.isTracked(insCode)
    }
}
