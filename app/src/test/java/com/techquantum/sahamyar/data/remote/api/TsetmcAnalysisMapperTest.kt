package com.techquantum.sahamyar.data.remote.api

import com.techquantum.sahamyar.data.remote.model.StockHistoryItem
import com.techquantum.sahamyar.data.remote.model.StockHistoryResponse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class TsetmcAnalysisMapperTest {

    private fun item(date: Long, closingPrice: Long?) = StockHistoryItem(
        date = date,
        change = null,
        closing_price = closingPrice,
        last_price = null,
        first_price = null,
        min_price = null,
        max_price = null,
        yesterday_price = null,
        trade_count = null,
        volume = null,
        value = null
    )

    private fun history(vararg items: StockHistoryItem) = StockHistoryResponse(
        source = "TSETMC",
        ins_code = "12345",
        count = items.size,
        items = items.toList(),
        retrieved_at = null
    )

    @Test
    fun countAndLatestDateUseOnlyValidClosingPriceRecords() {
        val input = history(
            item(20240101L, 1000L),
            item(20240102L, null),
            item(20240103L, 1100L),
            item(20240104L, 0L)
        )

        val result = TsetmcAnalysisMapper.analyze(input, 365)

        assertEquals(2, result.count)
        assertEquals(20240103L, result.latest_date)
    }

    @Test
    fun emptyHistoryProducesZeroCountAndNullLatestDate() {
        val result = TsetmcAnalysisMapper.analyze(history(), 365)

        assertEquals(0, result.count)
        assertNull(result.latest_date)
        assertEquals("INSUFFICIENT_DATA", result.analysis_status)
    }

    @Test
    fun allValidRecordsAreCounted() {
        val result = TsetmcAnalysisMapper.analyze(
            history(
                item(20240101L, 1000L),
                item(20240102L, 1050L),
                item(20240103L, 1025L)
            ),
            365
        )

        assertEquals(3, result.count)
        assertEquals(20240103L, result.latest_date)
    }

    @Test
    fun analysisCountLimitsTheConsideredHistoryWindow() {
        val result = TsetmcAnalysisMapper.analyze(
            history(
                item(20240101L, 1000L),
                item(20240102L, null),
                item(20240103L, 1050L)
            ),
            2
        )

        assertEquals(1, result.count)
        assertEquals(20240103L, result.latest_date)
    }

    @Test
    fun closeBasedIndicatorsUseOnlyTrailingContiguousValidPrices() {
        val beforeGap = (1L..10L).map { day ->
            item(20240100L + day, 1000L + day)
        }
        val afterGap = (12L..21L).map { day ->
            item(20240100L + day, 1000L + day)
        }

        val result = TsetmcAnalysisMapper.analyze(
            history(*(beforeGap + item(20240111L, null) + afterGap).toTypedArray()),
            365
        )

        assertEquals(20, result.count)
        assertEquals(20240121L, result.latest_date)
        assertNull(result.indicators?.sma?.get("20"))
        assertNull(result.indicators?.ema?.get("12"))
        assertNull(result.indicators?.rsi?.get("14"))
    }

}
