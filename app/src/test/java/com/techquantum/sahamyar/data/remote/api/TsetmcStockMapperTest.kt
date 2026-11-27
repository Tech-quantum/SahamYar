package com.techquantum.sahamyar.data.remote.api

import com.google.gson.JsonParser
import org.junit.Assert.*
import org.junit.Test

class TsetmcStockMapperTest {

    private fun json(value: String) =
        JsonParser.parseString(value).asJsonObject

    @Test
    fun detailMapsRealFooladPayload() {
        val raw = json(
            """
            {
              "insCode": "46348559193224090",
              "lVal18AFC": "فولاد",
              "lVal30": "فولاد مباركه اصفهان",
              "cIsin": "IRO1FOLD0009",
              "flow": 1,
              "flowTitle": "بازار بورس",
              "cgrValCot": "N1",
              "zTitad": 1935000000000.0,
              "baseVol": 1,
              "minWeek": 4900.0,
              "maxWeek": 5420.0,
              "minYear": 2182.0,
              "maxYear": 5420.0,
              "qTotTran5JAvg": 1985674252.0,
              "sector": {
                "lSecVal": "فلزات اساسي"
              },
              "eps": {
                "epsValue": null,
                "estimatedEPS": "693",
                "sectorPE": 11.2
              }
            }
            """.trimIndent()
        )

        val result = TsetmcStockMapper.detail("46348559193224090", raw)
        val item = result.item!!

        assertEquals("TSETMC", result.source)
        assertEquals("46348559193224090", item.ins_code)
        assertEquals("فولاد", item.symbol)
        assertEquals("فولاد مباركه اصفهان", item.name)
        assertEquals("IRO1FOLD0009", item.isin)
        assertEquals(1, item.market_flow)
        assertEquals("بازار بورس", item.market)
        assertEquals("فلزات اساسي", item.sector)
        assertEquals("COMMON_STOCK", item.instrument_category)
        assertEquals(1935000000000L, item.shares_count)
        assertEquals(1985674252L, item.average_volume)
        assertNull(item.fundamentals?.eps_actual)
        assertEquals(693.0, item.fundamentals?.eps_estimated ?: 0.0, 0.001)
        assertEquals(11.2, item.fundamentals?.sector_pe ?: 0.0, 0.001)
    }

    @Test
    fun priceMapsRealFooladPayload() {
        val raw = json(
            """
            {
              "finalLastDate": 20261125,
              "pClosing": 5420.0,
              "pDrCotVal": 5420.0,
              "priceFirst": 5380.0,
              "priceMin": 5340.0,
              "priceMax": 5420.0,
              "priceYesterday": 5270.0,
              "zTotTran": 11213.0,
              "qTotTran5J": 1160510213.0,
              "qTotCap": 6285533272870.0,
              "instrumentState": {
                "cEtavalTitle": "مجاز"
              }
            }
            """.trimIndent()
        )

        val result = TsetmcStockMapper.price("46348559193224090", raw)
        val item = result.item!!

        assertEquals("TSETMC", result.source)
        assertEquals("46348559193224090", result.ins_code)
        assertEquals(20261125L, item.date)
        assertEquals(5420L, item.closing_price)
        assertEquals(5420L, item.last_price)
        assertEquals(5380L, item.first_price)
        assertEquals(5340L, item.min_price)
        assertEquals(5420L, item.max_price)
        assertEquals(5270L, item.yesterday_price)
        assertEquals(11213L, item.trade_count)
        assertEquals(1160510213L, item.volume)
        assertEquals(6285533272870L, item.value)
        assertEquals("مجاز", item.state)
    }

    @Test
    fun priceRejectsInvalidDateAndFractionalIntegerFields() {
        val raw = json(
            """
            {
              "finalLastDate": 20260230,
              "pClosing": 5420.5,
              "pDrCotVal": 5300.0
            }
            """.trimIndent()
        )

        val item = TsetmcStockMapper.price("12345", raw).item!!

        assertNull(item.date)
        assertNull(item.closing_price)
        assertEquals(5300L, item.last_price)
    }

    @Test
    fun historyFiltersInvalidDatesSortsAndDeduplicates() {
        val raw = json(
            """
            {
              "closingPriceDaily": [
                {
                  "dEven": 20261125,
                  "pClosing": 5420.0
                },
                {
                  "dEven": 20261124,
                  "pClosing": 5270.0
                },
                {
                  "dEven": 20260230,
                  "pClosing": 5000.0
                },
                {
                  "dEven": 20261125,
                  "pClosing": 9999.0
                },
                123,
                {
                  "dEven": 20261126,
                  "pClosing": 5300.5
                }
              ]
            }
            """.trimIndent()
        )

        val result = TsetmcStockMapper.history("12345", raw, 10)

        assertEquals(2, result.count)
        assertEquals(
            listOf(20261124L, 20261126L),
            result.items.map { it.date }
        )
        assertEquals(5270L, result.items[0].closing_price)
        assertNull(result.items[1].closing_price)
    }

    @Test
    fun historyMergesComplementaryDuplicatesAndRejectsConflicts() {
        val raw = json(
            """
            {
              "closingPriceDaily": [
                {"dEven": 20261125, "pClosing": 5420},
                {"dEven": 20261125, "qTotTran5J": 1000},
                {"dEven": 20261124, "pClosing": 5200},
                {"dEven": 20261124, "pClosing": 5300}
              ]
            }
            """.trimIndent()
        )

        val result = TsetmcStockMapper.history("12345", raw, 10)

        assertEquals(1, result.count)
        assertEquals(20261125L, result.items.single().date)
        assertEquals(5420L, result.items.single().closing_price)
        assertEquals(1000L, result.items.single().volume)
    }

    @Test
    fun historyAppliesRequestedCountAfterSortingAndDeduplication() {
        val raw = json(
            """
            {
              "closingPriceDaily": [
                {"dEven": 20261123, "pClosing": 5100},
                {"dEven": 20261125, "pClosing": 5420},
                {"dEven": 20261124, "pClosing": 5270}
              ]
            }
            """.trimIndent()
        )

        val result = TsetmcStockMapper.history("12345", raw, 2)

        assertEquals(2, result.count)
        assertEquals(
            listOf(20261124L, 20261125L),
            result.items.map { it.date }
        )
    }

    @Test
    fun historyRejectsInvalidCountAndMissingPayload() {
        val validRaw = json("""{"closingPriceDaily": []}""")
        val missingRaw = json("""{"other": []}""")

        assertThrows(IllegalArgumentException::class.java) {
            TsetmcStockMapper.history("12345", validRaw, 0)
        }

        assertThrows(IllegalStateException::class.java) {
            TsetmcStockMapper.history("12345", missingRaw, 5)
        }
    }
}
