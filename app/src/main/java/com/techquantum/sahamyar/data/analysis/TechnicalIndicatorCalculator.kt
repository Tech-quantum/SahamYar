package com.techquantum.sahamyar.data.analysis

import kotlin.math.max

object TechnicalIndicatorCalculator {

    fun sma(values: List<Double>, period: Int): List<Double?> {
        require(period > 0)
        val result = MutableList<Double?>(values.size) { null }
        if (values.size < period) return result

        var sum = values.take(period).sum()
        result[period - 1] = sum / period

        for (i in period until values.size) {
            sum += values[i] - values[i - period]
            result[i] = sum / period
        }
        return result
    }

    fun ema(values: List<Double>, period: Int): List<Double?> {
        require(period > 0)
        val result = MutableList<Double?>(values.size) { null }
        if (values.size < period) return result

        val multiplier = 2.0 / (period + 1)
        var previous = values.take(period).average()
        result[period - 1] = previous

        for (i in period until values.size) {
            previous = (values[i] - previous) * multiplier + previous
            result[i] = previous
        }
        return result
    }

    fun rsi(values: List<Double>, period: Int = 14): List<Double?> {
        require(period > 0)
        val result = MutableList<Double?>(values.size) { null }
        if (values.size <= period) return result

        val gains = (1 until values.size).map {
            max(values[it] - values[it - 1], 0.0)
        }
        val losses = (1 until values.size).map {
            max(values[it - 1] - values[it], 0.0)
        }

        var avgGain = gains.take(period).average()
        var avgLoss = losses.take(period).average()

        fun value(gain: Double, loss: Double): Double = when {
            gain == 0.0 && loss == 0.0 -> 50.0
            loss == 0.0 -> 100.0
            gain == 0.0 -> 0.0
            else -> 100.0 - (100.0 / (1.0 + gain / loss))
        }

        result[period] = value(avgGain, avgLoss)

        for (i in period + 1 until values.size) {
            val changeIndex = i - 1
            avgGain = (avgGain * (period - 1) + gains[changeIndex]) / period
            avgLoss = (avgLoss * (period - 1) + losses[changeIndex]) / period
            result[i] = value(avgGain, avgLoss)
        }
        return result
    }

    data class MacdResult(
        val line: List<Double?>,
        val signal: List<Double?>,
        val histogram: List<Double?>
    )

    fun macd(
        values: List<Double>,
        fastPeriod: Int = 12,
        slowPeriod: Int = 26,
        signalPeriod: Int = 9
    ): MacdResult {
        require(fastPeriod > 0 && slowPeriod > 0 && signalPeriod > 0)
        require(fastPeriod < slowPeriod)

        val fast = ema(values, fastPeriod)
        val slow = ema(values, slowPeriod)
        val line = MutableList<Double?>(values.size) { null }

        for (i in values.indices) {
            val f = fast[i]
            val s = slow[i]
            if (f != null && s != null) line[i] = f - s
        }

        val valid = line.filterNotNull()
        val signalValues = ema(valid, signalPeriod)
        val signal = MutableList<Double?>(values.size) { null }
        val histogram = MutableList<Double?>(values.size) { null }
        val startIndex = slowPeriod - 1

        for (i in signalValues.indices) {
            val target = startIndex + i
            if (target >= values.size) break
            signal[target] = signalValues[i]
            val currentSignal = signalValues[i]
            if (currentSignal != null) {
                histogram[target] = line[target]?.minus(currentSignal)
            }
        }

        return MacdResult(line, signal, histogram)
    }
}
