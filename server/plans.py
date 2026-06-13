"""
Plan definitions — single source of truth for plan names and their limits.

Adding a new plan: add an entry here and update MAX_CHILDREN.
"""

from enum import Enum


class Plan(str, Enum):
    FREE    = "free"
    PREMIUM = "premium"


MAX_CHILDREN: dict[Plan, int] = {
    Plan.FREE:    1,
    Plan.PREMIUM: 999,
}
