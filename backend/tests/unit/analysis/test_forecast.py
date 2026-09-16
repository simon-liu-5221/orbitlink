"""AN-06 phase 2 acceptance tests for the forecast pure functions."""

from __future__ import annotations

import pytest

from app.analysis.forecast import MIN_HISTORY_POINTS, forecast_metric


def test_ac11_below_minimum_is_unavailable_not_a_fake_prediction() -> None:
    result = forecast_metric([1.0, 2.0, 3.0, 4.0])
    assert result.available is False
    assert result.predicted_next is None
    assert result.mae is None
    assert result.points_used == 4


def test_ac9_perfect_line_extrapolates_exactly() -> None:
    """y = 2x + 1 for x in 0..4 -> next point (x=5) should predict 11."""
    values = [1.0, 3.0, 5.0, 7.0, 9.0]
    result = forecast_metric(values)
    assert result.available is True
    assert result.predicted_next == pytest.approx(11.0)


def test_ac10_mae_is_real_leave_one_out_not_a_placeholder() -> None:
    """A perfect line has zero leave-one-out error; noise pushes it above zero."""
    perfect = forecast_metric([1.0, 3.0, 5.0, 7.0, 9.0])
    assert perfect.mae == pytest.approx(0.0, abs=1e-9)

    noisy = forecast_metric([1.0, 3.5, 4.5, 7.5, 8.5])
    assert noisy.mae is not None
    assert noisy.mae > 0.0


def test_points_used_matches_input_length_at_and_above_the_threshold() -> None:
    values = [float(i) for i in range(MIN_HISTORY_POINTS)]
    result = forecast_metric(values)
    assert result.available is True
    assert result.points_used == MIN_HISTORY_POINTS


def test_empty_input_is_unavailable() -> None:
    result = forecast_metric([])
    assert result.available is False
    assert result.points_used == 0


def test_flat_series_forecasts_the_flat_value() -> None:
    result = forecast_metric([5.0, 5.0, 5.0, 5.0, 5.0, 5.0])
    assert result.available is True
    assert result.predicted_next == pytest.approx(5.0)
    assert result.mae == pytest.approx(0.0, abs=1e-9)
