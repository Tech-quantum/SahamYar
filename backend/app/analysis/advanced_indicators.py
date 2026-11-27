"""Pure advanced technical indicators for SahamYar.

All returned series are aligned with the input data.
Unavailable values are represented by None.
No external numerical dependencies are required.
"""

import math
from collections.abc import Sequence


def _values(data, name, non_negative=False):
    if isinstance(data, (str, bytes)) or not isinstance(data, Sequence):
        raise ValueError(f"{name} must be a numeric sequence")

    result = []
    for value in data:
        if isinstance(value, bool):
            raise ValueError(f"{name} contains an invalid value")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            raise ValueError(f"{name} contains an invalid value") from None

        if not math.isfinite(number):
            raise ValueError(f"{name} must contain only finite values")
        if non_negative and number < 0:
            raise ValueError(f"{name} cannot contain negative values")

        result.append(number)

    return result


def _period(value, name="period"):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _positive_finite(value, name, allow_zero=False):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be finite")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{name} must be finite") from None

    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    if number < 0 or (number == 0 and not allow_zero):
        raise ValueError(f"{name} must be {'non-negative' if allow_zero else 'positive'}")
    return number


def _ohlc(high, low, close):
    high = _values(high, "high")
    low = _values(low, "low")
    close = _values(close, "close")

    if not (len(high) == len(low) == len(close)):
        raise ValueError("OHLC sequences must have equal lengths")

    for h, l, c in zip(high, low, close):
        if h < l:
            raise ValueError("high cannot be lower than low")
        if c < l or c > h:
            raise ValueError("close must be within the candle high/low range")

    return high, low, close


def _sma_optional(values, period):
    result = [None] * len(values)
    for index in range(period - 1, len(values)):
        window = values[index - period + 1:index + 1]
        if all(value is not None for value in window):
            result[index] = sum(window) / period
    return result


def bollinger_bands(values, period=20, stddev=2.0):
    """Return aligned upper, middle and lower Bollinger Band series.

    Standard deviation uses the population formula.
    """
    values = _values(values, "values")
    period = _period(period)
    multiplier = _positive_finite(stddev, "stddev", allow_zero=True)

    middle = _sma_optional(values, period)
    upper = [None] * len(values)
    lower = [None] * len(values)

    for index in range(period - 1, len(values)):
        window = values[index - period + 1:index + 1]
        mean = middle[index]
        variance = sum((item - mean) ** 2 for item in window) / period
        deviation = math.sqrt(variance)
        upper[index] = mean + multiplier * deviation
        lower[index] = mean - multiplier * deviation

    return {"upper": upper, "middle": middle, "lower": lower}


def atr(high, low, close, period=14):
    """Average True Range using Wilder smoothing.

    The first ATR is available at index `period`.
    """
    period = _period(period)
    high, low, close = _ohlc(high, low, close)
    result = [None] * len(close)

    if len(close) <= period:
        return result

    true_ranges = [None] * len(close)
    for index in range(1, len(close)):
        true_ranges[index] = max(
            high[index] - low[index],
            abs(high[index] - close[index - 1]),
            abs(low[index] - close[index - 1]),
        )

    first_atr = sum(true_ranges[1:period + 1]) / period
    result[period] = first_atr

    for index in range(period + 1, len(close)):
        result[index] = (
            result[index - 1] * (period - 1) + true_ranges[index]
        ) / period

    return result


def stochastic(high, low, close, k_period=14, d_period=3):
    """Return aligned Stochastic %K and %D series.

    A zero-range window produces neutral %K = 50.
    %D is the simple moving average of valid %K values.
    """
    k_period = _period(k_period, "k_period")
    d_period = _period(d_period, "d_period")
    high, low, close = _ohlc(high, low, close)

    k_values = [None] * len(close)

    for index in range(k_period - 1, len(close)):
        start = index - k_period + 1
        highest = max(high[start:index + 1])
        lowest = min(low[start:index + 1])
        price_range = highest - lowest

        if price_range == 0:
            k_values[index] = 50.0
        else:
            k_values[index] = (
                (close[index] - lowest) / price_range
            ) * 100.0

    d_values = _sma_optional(k_values, d_period)
    return {"k": k_values, "d": d_values}


def obv(close, volume):
    """On-Balance Volume. The first observation starts at zero."""
    close = _values(close, "close")
    volume = _values(volume, "volume", non_negative=True)

    if len(close) != len(volume):
        raise ValueError("close and volume sequences must have equal lengths")

    if not close:
        return []

    result = [0.0]
    for index in range(1, len(close)):
        if close[index] > close[index - 1]:
            result.append(result[-1] + volume[index])
        elif close[index] < close[index - 1]:
            result.append(result[-1] - volume[index])
        else:
            result.append(result[-1])

    return result


def volume_sma(volume, period=20):
    """Simple moving average of volume, aligned with the input."""
    volume = _values(volume, "volume", non_negative=True)
    period = _period(period)
    return _sma_optional(volume, period)


def volume_ratio(volume, period=20):
    """Current volume divided by the average of the previous N volumes.

    The current observation is deliberately excluded from the baseline.
    A zero baseline produces None.
    """
    volume = _values(volume, "volume", non_negative=True)
    period = _period(period)
    result = [None] * len(volume)

    for index in range(period, len(volume)):
        previous = volume[index - period:index]
        average = sum(previous) / period
        if average > 0:
            result[index] = volume[index] / average

    return result
