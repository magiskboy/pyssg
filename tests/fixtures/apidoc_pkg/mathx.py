"""NumPy-style numeric helpers."""

from __future__ import annotations


def clamp(value: float, low: float, high: float) -> float:
    """Clamp a value to a range.

    Parameters
    ----------
    value : float
        The value to clamp.
    low : float
        Lower bound.
    high : float
        Upper bound.

    Returns
    -------
    float
        The clamped value.
    """
    return max(low, min(value, high))
