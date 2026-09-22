"""Werktags-Arithmetik (Mo-Fr), Feiertage werden bewusst ignoriert."""

from __future__ import annotations

from datetime import date, timedelta


def is_business_day(day: date) -> bool:
    return day.weekday() < 5  # Montag=0 ... Freitag=4


def add_business_days(start: date, num_days: int) -> date:
    """Verschiebt `start` um genau `num_days` Werktage nach vorne.

    Wochenenden zaehlen nicht als Werktag und werden uebersprungen.
    """
    if num_days < 0:
        raise ValueError("num_days muss >= 0 sein.")

    current = start
    remaining = num_days
    while remaining > 0:
        current += timedelta(days=1)
        if is_business_day(current):
            remaining -= 1
    return current
