package com.techquantum.sahamyar.data.analysis

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test

class TechnicalIndicatorCalculatorTest {

    @Test
    fun smaReturnsNullUntilPeriodIsAvailable() {
        val result = TechnicalIndicatorCalculator.sma(listOf(10.0, 20.0, 30.0), 2)

        assertNull(result[0])
        assertEquals(15.0, result[1]!!, 0.000001)
        assertEquals(25.0, result[2]!!, 0.000001)
    }

    @Test
    fun smaReturnsAllNullWhenHistoryIsShorterThanPeriod() {
        val result = TechnicalIndicatorCalculator.sma(listOf(10.0, 20.0), 3)

        assertEquals(listOf(null, null), result)
    }

    @Test
    fun emaUsesInitialSimpleAverageAndThenAppliesMultiplier() {
        val result = TechnicalIndicatorCalculator.ema(listOf(10.0, 20.0, 30.0, 40.0), 3)

        assertNull(result[0])
        assertNull(result[1])
        assertEquals(20.0, result[2]!!, 0.000001)
        assertEquals(30.0, result[3]!!, 0.000001)
    }

    @Test
    fun rsiReturnsHundredForOnlyGains() {
        val result = TechnicalIndicatorCalculator.rsi(
            listOf(10.0, 11.0, 12.0, 13.0),
            period = 2
        )

        assertNull(result[0])
        assertNull(result[1])
        assertEquals(100.0, result[2]!!, 0.000001)
        assertEquals(100.0, result[3]!!, 0.000001)
    }

    @Test
    fun rsiReturnsZeroForOnlyLosses() {
        val result = TechnicalIndicatorCalculator.rsi(
            listOf(13.0, 12.0, 11.0, 10.0),
            period = 2
        )

        assertEquals(0.0, result[2]!!, 0.000001)
        assertEquals(0.0, result[3]!!, 0.000001)
    }

    @Test
    fun rsiReturnsFiftyWhenPricesDoNotChange() {
        val result = TechnicalIndicatorCalculator.rsi(
            listOf(10.0, 10.0, 10.0),
            period = 2
        )

        assertEquals(50.0, result[2]!!, 0.000001)
    }

    @Test
    fun rsiRequiresPeriodPlusOnePrices() {
        val result = TechnicalIndicatorCalculator.rsi(
            listOf(10.0, 11.0),
            period = 2
        )

        assertEquals(listOf(null, null), result)
    }

    @Test
    fun macdSignalStartsAfterSlowEmaAndSignalPeriod() {
        val values = (1..40).map { it.toDouble() }
        val result = TechnicalIndicatorCalculator.macd(
            values,
            fastPeriod = 3,
            slowPeriod = 5,
            signalPeriod = 2
        )

        assertNull(result.line[3])
        assertEquals(1.0, result.line[4]!!, 0.000001)
        assertNull(result.signal[4])
        assertEquals(1.0, result.signal[5]!!, 0.000001)
        assertEquals(0.0, result.histogram[5]!!, 0.000001)
    }

    @Test
    fun macdReturnsNoSignalWhenHistoryIsInsufficient() {
        val result = TechnicalIndicatorCalculator.macd(
            listOf(10.0, 11.0, 12.0, 13.0, 14.0),
            fastPeriod = 3,
            slowPeriod = 5,
            signalPeriod = 2
        )

        assertEquals(listOf(null, null, null, null, 1.0), result.line)
        assertTrueAllNull(result.signal)
        assertTrueAllNull(result.histogram)
    }

    @Test
    fun smaRejectsZeroPeriod() {
        assertThrows(IllegalArgumentException::class.java) {
            TechnicalIndicatorCalculator.sma(listOf(1.0), 0)
        }
    }

    @Test
    fun macdRejectsInvalidPeriodOrder() {
        assertThrows(IllegalArgumentException::class.java) {
            TechnicalIndicatorCalculator.macd(
                listOf(1.0, 2.0, 3.0),
                fastPeriod = 5,
                slowPeriod = 3,
                signalPeriod = 2
            )
        }
    }

    private fun assertTrueAllNull(values: List<Double?>) {
        values.forEach { assertNull(it) }
    }
}
