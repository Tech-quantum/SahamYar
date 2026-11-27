package com.techquantum.sahamyar.data.analysis

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.sqrt

object AdvancedTechnicalIndicators {

    data class BollingerResult(
        val upper: List<Double?>,
        val middle: List<Double?>,
        val lower: List<Double?>
    )

    data class StochasticResult(
        val k: List<Double?>,
        val d: List<Double?>
    )

    private fun smaOptional(
        values: List<Double?>,
        period: Int
    ): List<Double?> {
        require(period > 0)
        val result = MutableList<Double?>(values.size) { null }

        for (i in period - 1 until values.size) {
            val window = values.subList(i - period + 1, i + 1)
            if (window.all { it != null }) {
                result[i] = window.filterNotNull().average()
            }
        }
        return result
    }

    fun bollinger(
        values: List<Double>,
        period: Int = 20,
        stddev: Double = 2.0
    ): BollingerResult {
        require(period > 0)
        require(stddev.isFinite() && stddev >= 0.0)

        val middle = smaOptional(values.map { it }, period)
        val upper = MutableList<Double?>(values.size) { null }
        val lower = MutableList<Double?>(values.size) { null }

        for (i in period - 1 until values.size) {
            val window = values.subList(i - period + 1, i + 1)
            val mean = middle[i] ?: continue
            val variance = window.sumOf {
                val difference = it - mean
                difference * difference
            } / period
            val deviation = sqrt(variance)
            upper[i] = mean + stddev * deviation
            lower[i] = mean - stddev * deviation
        }

        return BollingerResult(upper, middle, lower)
    }

    fun atr(
        high: List<Double>,
        low: List<Double>,
        close: List<Double>,
        period: Int = 14
    ): List<Double?> {
        validateOhlc(high, low, close)
        require(period > 0)

        val result = MutableList<Double?>(close.size) { null }
        if (close.size <= period) return result

        val trueRanges = MutableList<Double?>(close.size) { null }

        for (i in 1 until close.size) {
            trueRanges[i] = maxOf(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1])
            )
        }

        var previous = trueRanges.subList(1, period + 1)
            .filterNotNull().average()
        result[period] = previous

        for (i in period + 1 until close.size) {
            previous = (
                previous * (period - 1) + trueRanges[i]!!
            ) / period
            result[i] = previous
        }

        return result
    }

    fun stochastic(
        high: List<Double>,
        low: List<Double>,
        close: List<Double>,
        kPeriod: Int = 14,
        dPeriod: Int = 3
    ): StochasticResult {
        validateOhlc(high, low, close)
        require(kPeriod > 0 && dPeriod > 0)

        val k = MutableList<Double?>(close.size) { null }

        for (i in kPeriod - 1 until close.size) {
            val start = i - kPeriod + 1
            val highest = high.subList(start, i + 1).maxOrNull()!!
            val lowest = low.subList(start, i + 1).minOrNull()!!
            val range = highest - lowest

            k[i] = if (range == 0.0) {
                50.0
            } else {
                ((close[i] - lowest) / range) * 100.0
            }
        }

        return StochasticResult(k, smaOptional(k, dPeriod))
    }

    fun obv(
        close: List<Double>,
        volume: List<Double>
    ): List<Double> {
        require(close.size == volume.size)
        require(volume.all { it.isFinite() && it >= 0.0 })

        if (close.isEmpty()) return emptyList()

        val result = MutableList(close.size) { 0.0 }

        for (i in 1 until close.size) {
            result[i] = when {
                close[i] > close[i - 1] ->
                    result[i - 1] + volume[i]
                close[i] < close[i - 1] ->
                    result[i - 1] - volume[i]
                else -> result[i - 1]
            }
        }
        return result
    }

    fun volumeSma(
        volume: List<Double>,
        period: Int = 20
    ): List<Double?> {
        require(period > 0)
        require(volume.all { it.isFinite() && it >= 0.0 })
        return smaOptional(volume.map { it }, period)
    }

    fun volumeRatio(
        volume: List<Double>,
        period: Int = 20
    ): List<Double?> {
        require(period > 0)
        require(volume.all { it.isFinite() && it >= 0.0 })

        val result = MutableList<Double?>(volume.size) { null }

        for (i in period until volume.size) {
            val average = volume.subList(i - period, i).average()
            if (average > 0.0) {
                result[i] = volume[i] / average
            }
        }
        return result
    }

    private fun validateOhlc(
        high: List<Double>,
        low: List<Double>,
        close: List<Double>
    ) {
        require(high.size == low.size && low.size == close.size)
        require(
            (high + low + close).all { it.isFinite() }
        )

        for (i in close.indices) {
            require(high[i] >= low[i])
            require(close[i] >= low[i] && close[i] <= high[i])
        }
    }
}
