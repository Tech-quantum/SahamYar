import math

import pytest

from app.analysis.advanced_indicators import (
    atr,
    bollinger_bands,
    obv,
    stochastic,
    volume_ratio,
    volume_sma,
)


def test_bollinger_bands_population_standard_deviation():
    result = bollinger_bands([1, 2, 3, 4], period=3, stddev=2)

    deviation = math.sqrt(2 / 3)
    assert result["middle"] == [None, None, 2.0, 3.0]
    assert result["upper"][2] == pytest.approx(2 + 2 * deviation)
    assert result["lower"][2] == pytest.approx(2 - 2 * deviation)
    assert result["upper"][3] == pytest.approx(3 + 2 * deviation)


def test_bollinger_insufficient_data():
    result = bollinger_bands([10, 11], period=3)
    assert result == {
        "upper": [None, None],
        "middle": [None, None],
        "lower": [None, None],
    }


def test_bollinger_zero_deviation():
    result = bollinger_bands([2, 4, 6], period=3, stddev=0)
    assert result["upper"][2] == 4
    assert result["lower"][2] == 4


def test_atr_wilder_smoothing():
    high = [10, 12, 14, 15]
    low = [8, 9, 10, 11]
    close = [9, 11, 13, 14]

    result = atr(high, low, close, period=2)

    assert result[:2] == [None, None]
    assert result[2] == pytest.approx(3.5)
    assert result[3] == pytest.approx(3.75)


def test_atr_insufficient_data():
    assert atr([10, 11], [8, 9], [9, 10], period=2) == [None, None]


def test_atr_equal_high_low_is_valid():
    result = atr([10, 10, 10], [10, 10, 10], [10, 10, 10], period=2)
    assert result == [None, None, 0.0]


def test_stochastic_k_and_d_alignment():
    result = stochastic(
        high=[10, 12, 13, 14],
        low=[8, 9, 10, 11],
        close=[9, 11, 12, 13],
        k_period=2,
        d_period=2,
    )

    assert result["k"][:1] == [None]
    assert result["k"][1:] == pytest.approx([75, 75, 75])
    assert result["d"][:2] == [None, None]
    assert result["d"][2:] == pytest.approx([75, 75])


def test_stochastic_zero_range_is_neutral():
    result = stochastic(
        high=[10, 10, 10],
        low=[10, 10, 10],
        close=[10, 10, 10],
        k_period=2,
        d_period=2,
    )
    assert result["k"] == [None, 50, 50]
    assert result["d"] == [None, None, 50]


def test_stochastic_insufficient_data():
    result = stochastic([10], [8], [9], k_period=2, d_period=2)
    assert result == {"k": [None], "d": [None]}


def test_obv_increase_decrease_and_flat():
    assert obv(
        close=[10, 12, 12, 9, 11],
        volume=[100, 20, 30, 40, 50],
    ) == [0, 20, 20, -20, 30]


def test_obv_empty_input():
    assert obv([], []) == []


def test_volume_sma():
    assert volume_sma([10, 20, 30, 40], period=2) == [
        None, 15, 25, 35
    ]


def test_volume_ratio_uses_previous_period_only():
    assert volume_ratio([10, 20, 30, 60], period=2) == [
        None, None, 2.0, 2.4
    ]


def test_volume_ratio_zero_baseline():
    assert volume_ratio([0, 0, 10], period=2) == [None, None, None]


@pytest.mark.parametrize("function,args", [
    (bollinger_bands, ([1, 2],)),
    (volume_sma, ([1, 2],)),
    (volume_ratio, ([1, 2],)),
])
def test_invalid_period_rejected(function, args):
    with pytest.raises(ValueError):
        function(*args, period=0)


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_values_rejected(bad_value):
    with pytest.raises(ValueError):
        bollinger_bands([1, bad_value, 3], period=2)


def test_negative_volume_rejected():
    with pytest.raises(ValueError):
        volume_sma([10, -1, 20], period=2)


def test_boolean_values_rejected():
    with pytest.raises(ValueError):
        volume_ratio([10, True, 20], period=2)


def test_ohlc_length_mismatch_rejected():
    with pytest.raises(ValueError):
        atr([10, 11], [8], [9, 10], period=1)


def test_invalid_candle_rejected():
    with pytest.raises(ValueError):
        atr([8, 7], [10, 6], [9, 6], period=1)


def test_close_outside_candle_rejected():
    with pytest.raises(ValueError):
        stochastic([10, 11], [8, 9], [9, 12], k_period=1)


def test_obv_length_mismatch_rejected():
    with pytest.raises(ValueError):
        obv([10, 11], [100])


def test_invalid_standard_deviation_rejected():
    with pytest.raises(ValueError):
        bollinger_bands([1, 2, 3], period=2, stddev=-1)
