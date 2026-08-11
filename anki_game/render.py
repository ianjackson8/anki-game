"""Small terminal-rendering helpers shared between game screens (HP/lives
bars) and the stats screen (bar charts)."""

from __future__ import annotations


def bar(current: float, maximum: float, width: int = 24, fill: str = "█", empty: str = "░") -> str:
    if maximum <= 0:
        return empty * width
    filled = max(0, min(width, round(width * current / maximum)))
    return fill * filled + empty * (width - filled)


def bar_chart(rows: list[tuple[str, float, float]], *, width: int = 24, value_fmt: str = "{:.0f}") -> str:
    """rows: (label, value, max_value) -- max_value may differ per row (e.g.
    scale every row against the deck size) or be the same for all (e.g. a
    0-100 percentage scale). Returns an aligned multi-line string."""
    if not rows:
        return "(no data yet)"
    label_width = max(len(label) for label, _, _ in rows)
    lines = []
    for label, value, maximum in rows:
        lines.append(
            f"{label:<{label_width}}  {bar(value, maximum, width=width)}  {value_fmt.format(value)}"
        )
    return "\n".join(lines)
