import pytest

from app.analysis.indicators import ema, macd, rsi, sma


def test_sma_calculates_moving_average():
    assert sma([1, 2, 3, 4, 5], 3) == [
        None, None, 2.0, 3.0, 4.0
    ]


def test_ema_calculates_exponential_average():
    assert ema([1, 2, 3, 4, 5], 3) == [
        None, None, 2.0, 3.0, 4.0
    ]


def test_sma_returns_none_when_data_is_insufficient():
    assert sma([10, 20], 3) == [None, None]


def test_ema_returns_none_when_data_is_insufficient():
    assert ema([10, 20], 3) == [None, None]


@pytest.mark.parametrize("period", [0, -1, 1.5, True])
def test_invalid_period_raises_value_error(period):
    with pytest.raises(ValueError):
        sma([1, 2, 3], period)


def test_non_finite_values_raise_value_error():
    with pytest.raises(ValueError):
        sma([1, float("nan"), 3], 2)


def test_rsi_returns_100_for_rising_prices():
    assert rsi([1, 2, 3, 4, 5], 3)[3] == 100.0


def test_rsi_returns_zero_for_falling_prices():
    assert rsi([5, 4, 3, 2, 1], 3)[3] == 0.0


def test_rsi_returns_50_for_flat_prices():
    assert rsi([10, 10, 10, 10, 10], 3)[3] == 50.0


def test_rsi_returns_none_when_data_is_insufficient():
    assert rsi([10, 20, 30], 3) == [None, None, None]


def test_macd_calculates_all_components():
    result = macd(
        list(range(1, 41)),
        fast_period=3,
        slow_period=5,
        signal_period=2,
    )

    assert len(result["macd"]) == 40
    assert len(result["signal"]) == 40
    assert len(result["histogram"]) == 40
    assert result["macd"][3] is None
    assert result["signal"][4] is None
    assert result["signal"][5] is not None
    assert result["histogram"][5] == pytest.approx(0.0)


def test_macd_rejects_invalid_period_order():
    with pytest.raises(ValueError):
        macd([1, 2, 3], fast_period=5, slow_period=3)


def test_macd_returns_none_when_data_is_insufficient():
    result = macd([1, 2, 3], fast_period=2, slow_period=3, signal_period=2)

    assert all(value is None for value in result["signal"])
    assert all(value is None for value in result["histogram"])


def test_macd_matches_reference_values():
    result = macd(
        [1, 2, 3, 2, 1, 2, 3, 4, 3, 2],
        fast_period=2,
        slow_period=3,
        signal_period=2,
    )

    assert result["macd"][2] == pytest.approx(0.5)
    assert result["macd"][3] == pytest.approx(1 / 6)
    assert result["signal"][3] == pytest.approx(1 / 3)
    assert result["histogram"][3] == pytest.approx(-1 / 6)
