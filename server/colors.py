"""
ANSI Color Codes for Terminal Output.

Provides consistent terminal color formatting across server log output.
"""


class Colors:
    """ANSI color codes for terminal output formatting."""

    # Reset and styles
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Bright (high-intensity) colors — codes 90-97
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"

    # Standard-intensity colors — codes 30-37
    DARK_RED = "\033[31m"
    DARK_MAGENTA = "\033[35m"
    DARK_CYAN = "\033[36m"

    # Background colors
    BG_RED = "\033[101m"
    BG_GREEN = "\033[102m"
    BG_YELLOW = "\033[103m"
    BG_CYAN = "\033[106m"
