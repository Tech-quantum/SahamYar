import math
from collections.abc import Sequence


def _validate_inputs(values: Sequence[float], period: int) -> list[float]:
    if isinstance(period, bool) or not isinstance(period, int) or period < 1:
        raise ValueError("period must be a positive integer")

    data = [float(value) for value in values]

    if any(not math.isfinite(value) for value in data):
        raise ValueError("values must contain only finite numbers")

    return data


def sma(values: Sequence[float], period: int) -> list[float | None]:
    """Calculate Simple Moving Average."""
    data = _validate_inputs(values, period)
    result: list[float | None] = [None] * len(data)

    if len(data) < period:
        return result

    window_sum = sum(data[:period])
    result[period - 1] = window_sum / period

    for index in range(period, len(data)):
        window_sum += data[index] - data[index - period]
        result[index] = window_sum / period

    return result


def ema(values: Sequence[float], period: int) -> list[float | None]:
    """Calculate Exponential Moving Average using an SMA seed."""
    data = _validate_inputs(values, period)
    result: list[float | None] = [None] * len(data)

    if len(data) < period:
        return result

    multiplier = 2 / (period + 1)
    previous = sum(data[:period]) / period
    result[period - 1] = previous

    for index in range(period, len(data)):
        previous = (data[index] - previous) * multiplier + previous
        result[index] = previous

    return result


def rsi(values: Sequence[float], period: int = 14) -> list[float | None]:
    """Calculate Relative Strength Index using Wilder's smoothing."""
    data = _validate_inputs(values, period)
    result: list[float | None] = [None] * len(data)

    if len(data) <= period:
        return result

    gains = [
        max(data[index] - data[index - 1], 0.0)
        for index in range(1, len(data))
    ]
    losses = [
        max(data[index - 1] - data[index], 0.0)
        for index in range(1, len(data))
    ]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def calculate_value(gain: float, loss: float) -> float:
        if gain == 0 and loss == 0:
            return 50.0
        if loss == 0:
            return 100.0
        if gain == 0:
            return 0.0
        return 100 - (100 / (1 + gain / loss))

    result[period] = calculate_value(avg_gain, avg_loss)

    for index in range(period + 1, len(data)):
        change_index = index - 1
        avg_gain = (
            avg_gain * (period - 1) + gains[change_index]
        ) / period
        avg_loss = (
            avg_loss * (period - 1) + losses[change_index]
        ) / period
        result[index] = calculate_value(avg_gain, avg_loss)

    return result


def macd(
    values: Sequence[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> dict[str, list[float | None]]:
    """Calculate MACD line, signal line, and histogram."""
    data = _validate_inputs(values, fast_period)
    _validate_inputs(data, slow_period)
    _validate_inputs(data, signal_period)

    if fast_period >= slow_period:
        raise ValueError("fast_period must be smaller than slow_period")

    fast_ema = ema(data, fast_period)
    slow_ema = ema(data, slow_period)

    macd_line: list[float | None] = [None] * len(data)

    for index in range(len(data)):
        if fast_ema[index] is not None and slow_ema[index] is not None:
            macd_line[index] = fast_ema[index] - slow_ema[index]

    valid_values = [
        value for value in macd_line if value is not None
    ]
    signal_values = ema(valid_values, signal_period)

    signal_line: list[float | None] = [None] * len(data)
    histogram: list[float | None] = [None] * len(data)

    start_index = slow_period - 1

    for index, signal in enumerate(signal_values):
        target_index = start_index + index
        signal_line[target_index] = signal

        if signal is not None:
            histogram[target_index] = (
                macd_line[target_index] - signal
            )

    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram,
    }
