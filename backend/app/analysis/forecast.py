"""Historical trend extrapolation (AN-06 phase 2).

Deliberately simple: ordinary least-squares linear regression against the
analysis sequence (0, 1, 2, ...), extrapolated one step past the last point.
No ARIMA, no Prophet, no injected model — the honesty is the point (see the
spec's "out of scope" list). The one number worth trusting here is ``mae``,
a real leave-one-out cross-validation error, not a made-up confidence figure.

Public entry point: :func:`forecast_metric`.
"""

from __future__ import annotations

import numpy as np

from app.analysis.types import MetricForecast

#: Below this many usable points, a linear fit is more noise than signal —
#: the UI shows "need N more analyses" instead (AC-11).
MIN_HISTORY_POINTS = 5


def _fit_predict(xs: np.ndarray, ys: np.ndarray, at: float) -> float:
    """Least-squares slope/intercept for ``ys ~ xs``, evaluated at ``at``."""
    slope, intercept = np.polyfit(xs, ys, deg=1)
    return float(slope * at + intercept)


def forecast_metric(values: list[float]) -> MetricForecast:
    """Extrapolate one step past ``values`` (index order = analysis order).

    ``mae`` is computed by leave-one-out cross-validation: for each point,
    refit on every other point and measure the error predicting the held-out
    one, then average — not a single in-sample residual.
    """
    n = len(values)
    if n < MIN_HISTORY_POINTS:
        return MetricForecast(available=False, predicted_next=None, mae=None, points_used=n)

    xs = np.arange(n, dtype=float)
    ys = np.array(values, dtype=float)

    predicted_next = _fit_predict(xs, ys, at=float(n))

    errors = np.empty(n)
    for i in range(n):
        train_xs = np.delete(xs, i)
        train_ys = np.delete(ys, i)
        errors[i] = abs(_fit_predict(train_xs, train_ys, at=xs[i]) - ys[i])
    mae = float(errors.mean())

    return MetricForecast(available=True, predicted_next=predicted_next, mae=mae, points_used=n)
