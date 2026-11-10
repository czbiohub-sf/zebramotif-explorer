"""Log-odds and information-content sequence logos for the ZebraMotif dashboard.

A PPM is stored as an (L, 4) probability matrix (columns A, C, G, T). This module turns
one into a Plotly logo using either positive log2(p / 0.25) enrichment weights or
information-content heights, p * (2 + sum(p * log2(p))). Both use a uniform background.
Letter glyphs are real font outlines (DejaVu Sans Bold) flattened to polygons once at
import, then stretched into each column with Plotly filled traces.
"""

import numpy as np
import plotly.graph_objects as go
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath

from zebramotif.utils import BASES, format_number, nucleotide_color_dict

_COLORS = nucleotide_color_dict()
_FONT = FontProperties(family="DejaVu Sans", weight="bold")
BACKGROUND = 0.25  # uniform per-base background frequency
MAX_BITS = 2.0  # tallest possible stack in either display scale


def _polygon_area(poly: np.ndarray) -> float:
    """Signed shoelace area of a closed polygon."""
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def _letter_polygons(letter: str) -> list:
    """
    Return a letter's outline as polygons normalized to the unit box.

    Each polygon is flagged as body or hole (e.g. the counter of an "A") so the caller can
    fill the body in the base color and punch the hole back out in the background color.

    Args:
        letter: Single character to render.

    Returns:
        list of (poly, is_hole) where poly is an (N, 2) array in [0, 1] x [0, 1].
    """

    tp = TextPath((0, 0), letter, size=1, prop=_FONT)
    polys = [np.asarray(p) for p in tp.to_polygons() if len(p) >= 3]
    if not polys:
        return []

    all_pts = np.vstack(polys)
    mins = all_pts.min(axis=0)
    span = np.where((all_pts.max(axis=0) - mins) == 0, 1.0, all_pts.max(axis=0) - mins)

    norm = [(p - mins) / span for p in polys]
    # Largest-area polygon is the body; anything else is an interior hole (the "A" counter).
    body_idx = int(np.argmax([_polygon_area(p) for p in norm]))
    return [(p, i != body_idx) for i, p in enumerate(norm)]


# Flatten each base's glyph once at import.
_GLYPHS = {b: _letter_polygons(b) for b in BASES}


def log_odds_weights(ppm: np.ndarray) -> np.ndarray:
    """
    Per-base log-odds weights in bits for an (L, 4) probability matrix.

    Matches logomaker's "weight" matrix type: weight_b = log2(p_b / background) against a
    uniform background of 0.25. Negative weights (bases rarer than background) are clipped
    to zero so only enriched bases are drawn.

    Args:
        ppm: (L, 4) array of base probabilities (rows sum to ~1).

    Returns:
        (L, 4) array of non-negative log-odds weights (bits) per base.
    """

    p = np.clip(ppm, 1e-9, 1.0)
    weights = np.log2(p / BACKGROUND)
    return np.clip(weights, 0.0, None)


def information_content_weights(ppm: np.ndarray) -> np.ndarray:
    """Per-base heights p_b * IC for a probability matrix, with IC = 2 - entropy.

    Zero probabilities contribute zero to the entropy without adding pseudocounts.
    A column's total height is its information content against a uniform background.
    """
    p = np.clip(np.asarray(ppm, dtype=float), 0.0, 1.0)
    log_p = np.zeros_like(p)
    np.log2(p, out=log_p, where=p > 0)
    information = np.clip(MAX_BITS + (p * log_p).sum(axis=1), 0.0, MAX_BITS)
    return p * information[:, None]


def _add_letter(
    fig: go.Figure,
    letter: str,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    visible: bool = True,
):
    """Add one scaled letter glyph (filled polygons) to the figure."""
    color = _COLORS[letter]
    for poly, is_hole in _GLYPHS[letter]:
        xs = x0 + poly[:, 0] * (x1 - x0)
        ys = y0 + poly[:, 1] * (y1 - y0)
        xs = np.append(xs, xs[0])
        ys = np.append(ys, ys[0])
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                fill="toself",
                fillcolor="white" if is_hole else color,
                line=dict(width=0),
                hoverinfo="skip",
                showlegend=False,
                visible=visible,
            )
        )


def reverse_complement(ppm: np.ndarray) -> np.ndarray:
    """Reverse complement of an (L, 4) A,C,G,T probability matrix.

    Reverses the position order and the base axis at once: with columns ordered A,C,G,T,
    reversing the base axis maps each column to its complement (A↔T, C↔G).
    """
    return np.asarray(ppm, dtype=float)[::-1, ::-1]


def _add_logo_traces(
    fig: go.Figure,
    ppm: np.ndarray,
    visible: bool,
    position_offset: int = 0,
    scale: str = "ic",
) -> int:
    """Add one orientation's letter glyphs + transparent hover bars. Returns trace count added."""
    n_before = len(fig.data)
    length = ppm.shape[0]
    weights = (
        information_content_weights(ppm) if scale == "ic" else log_odds_weights(ppm)
    )
    score_label = "Information content" if scale == "ic" else "Stacked log-odds"

    for i in range(length):
        heights = weights[i]
        order = np.argsort(heights)  # stack smallest at the bottom
        y = 0.0
        for j in order:
            h = heights[j]
            if h <= 1e-3:
                continue
            _add_letter(
                fig,
                BASES[j],
                position_offset + i + 0.08,
                position_offset + i + 0.92,
                y,
                y + h,
                visible=visible,
            )
            y += h

    # Transparent full-height hover bars: one per position, so hovering anywhere within a
    # column (not just the top) surfaces that position's base composition.
    hover_x, hover_text = [], []
    for i in range(length):
        hover_x.append(position_offset + i + 0.5)
        comp = "<br>".join(
            f"{BASES[j]}: {format_number(ppm[i, j])}" for j in np.argsort(ppm[i])[::-1]
        )
        hover_text.append(
            f"<b>Position {position_offset + i + 1}</b><br>"
            f"{score_label}: {format_number(weights[i].sum())} bits<br>{comp}"
        )
    fig.add_trace(
        go.Bar(
            x=hover_x,
            y=[MAX_BITS] * length,
            width=1.0,
            marker=dict(color="rgba(0,0,0,0)", line=dict(width=0)),
            hovertemplate="%{text}<extra></extra>",
            text=hover_text,
            textposition="none",
            showlegend=False,
            visible=visible,
        )
    )
    return len(fig.data) - n_before


def plot_logo(
    ppm,
    title: str | None = None,
    height: int = 300,
    *,
    position_offset: int = 0,
    position_range: tuple[int, int] | None = None,
    show_reverse_complement: bool = True,
    scale: str = "ic",
) -> go.Figure:
    """
    Sequence logo for a single PPM, with log-odds or information-content heights.

    Args:
        ppm: (L, 4) probability matrix, columns A, C, G, T.
        title: Optional title shown above the logo.
        height: Figure height in pixels.
        position_offset: Zero-based position of the first base in a shared frame.
        position_range: Shared (start, end) column boundaries, end exclusive. Unoccupied
            flanks stay blank, without fabricated bases or hover values.
        show_reverse_complement: Include a per-logo reverse-complement toggle. Disable
            when the caller controls the orientation of a group of aligned logos.
        scale: "ic" for probability-weighted information content in bits (the default),
            or "log_odds" for positive log2(p / 0.25) weights.

    Returns:
        Plotly Figure.
    """

    if scale not in {"ic", "log_odds"}:
        raise ValueError(f"Unknown logo scale: {scale!r}")
    ppm = np.asarray(ppm, dtype=float)
    length = ppm.shape[0]
    start, end = position_range or (position_offset, position_offset + length)
    # Wide aligned windows need fewer labels to stay readable in alternate cards.
    # Keep ticks anchored to the primary's first position; every base is still drawn.
    tick_step = max(1, (end - start + 15) // 16)
    tick_positions = [i for i in range(start, end) if i % tick_step == 0]

    fig = go.Figure()
    n_fwd = _add_logo_traces(
        fig, ppm, visible=True, position_offset=position_offset, scale=scale
    )
    n_rev = 0
    if show_reverse_complement:
        # Reflect the entire shared window, including any unoccupied flanks.
        n_rev = _add_logo_traces(
            fig,
            reverse_complement(ppm),
            visible=False,
            position_offset=start + end - position_offset - length,
            scale=scale,
        )
    fwd_visible = [True] * n_fwd + [False] * n_rev
    rev_visible = [False] * n_fwd + [True] * n_rev

    fig.update_layout(
        xaxis=dict(
            title="Position",
            range=[start, end],
            tickmode="array",
            tickvals=[i + 0.5 for i in tick_positions],
            ticktext=[str(i + 1) for i in tick_positions],
            showgrid=False,
            zeroline=False,
        ),
        yaxis=dict(
            title=(
                "Information content (bits)"
                if scale == "ic"
                else "Enrichment, log₂(p/0.25)"
            ),
            range=[0, MAX_BITS],
            dtick=0.5,
            showgrid=False,
            zeroline=False,
        ),
        barmode="overlay",
        plot_bgcolor="white",
        paper_bgcolor="white",
        font={"color": "#0D0001"},
        margin=dict(l=55, r=20, t=50 if title else 42, b=45),
        height=height,
        hovermode="closest",
        updatemenus=[
            dict(
                type="buttons",
                direction="left",
                showactive=True,
                active=-1,  # no button pre-applied, so the first click flips to reverse
                x=1.0,
                xanchor="right",
                y=1.0,
                yanchor="bottom",
                pad=dict(t=2, b=2, l=2, r=2),
                # Plotly menu buttons are SVG, not DOM, so they can't read the CSS theme
                # tokens. Match the near-black controls (see assets/styles.css).
                bgcolor="#FFFFFF",
                bordercolor="#0D0001",
                borderwidth=1,
                font=dict(size=11, color="#0D0001"),
                buttons=[
                    # Single toggle: args flips to reverse complement, args2 flips back.
                    dict(
                        label="Reverse complement",
                        method="update",
                        args=[{"visible": rev_visible}],
                        args2=[{"visible": fwd_visible}],
                    ),
                ],
            )
        ]
        if show_reverse_complement
        else [],
    )
    if title:
        fig.update_layout(
            title=dict(text=title, font=dict(size=13), x=0.5, xanchor="center")
        )
    return fig
