"""TF search layout, result rendering, and coordinated selection callbacks."""

import dash
import dash_bootstrap_components as dbc
import dash_molstar
import numpy as np
import pandas as pd
from dash import Input, Output, State, ctx, dcc, html
from dash.exceptions import PreventUpdate

from zebramotif import data as catalog
from zebramotif import structure_viewer
from zebramotif.downloads import DOWNLOADS_ENABLED
from zebramotif.navigation import synchronize_tf_search
from zebramotif.plot_logo import plot_logo, reverse_complement
from zebramotif.utils import as_pwm, base_gene_dbid, display_tf_name, format_number


def build_search_examples():
    """Offer family examples with confident structures and strong reference matches."""
    return html.Div(
        [
            html.Span("Try an example:", className="search-examples-label"),
            dcc.Link("sp2 (zf-C2H2)", href="/search?tf=ENSDARG00000076763"),
            dcc.Link("hoxb6a (Homeobox)", href="/search?tf=ENSDARG00000010630"),
            dcc.Link("usf1 (bHLH)", href="/search?tf=ENSDARG00000041689"),
        ],
        className="search-examples",
        **{"aria-label": "Example transcription factor searches"},
    )


layout = html.Div(
    children=[
        dcc.Location(id="search-url", refresh=False),
        dcc.Store(id="search-link-state", data=None),
        dcc.Store(id="search-result-selection", data=None),
        html.Header(
            style={"textAlign": "center", "marginBottom": "15px"},
            children=[
                html.H1("Search Zebrafish Motifs", style={"color": "var(--heading)"}),
            ],
        ),
        dbc.Row(
            dbc.Col(
                html.Div(
                    dcc.Dropdown(
                        id="tf-dropdown",
                        options=catalog.DROPDOWN_OPTIONS,
                        value=None,
                        placeholder="Search a transcription factor (gene symbol or Ensembl ID)...",
                        searchable=True,
                        clearable=True,
                        optionHeight=44,
                        maxHeight=400,
                    ),
                    className="tf-search-dropdown",
                    style={"maxWidth": "520px", "margin": "0 auto"},
                ),
                width=12,
            ),
            className="mb-3",
        ),
        build_search_examples(),
        html.Div(
            id="search-link-message",
            role="status",
            **{"aria-live": "polite"},
            style={"textAlign": "center", "color": "var(--text-muted)"},
        ),
        html.Section(
            [
                html.H2("What can you explore?", id="search-empty-heading"),
                html.P(
                    "Search a TF or try an example to explore its motifs, structure, "
                    "and supporting evidence.",
                    className="search-empty-intro",
                ),
                html.Div(
                    [
                        html.Div([html.H3(title), html.P(description)])
                        for title, description in [
                            (
                                "DNA-binding motifs",
                                "See which bases are preferred at each DNA position. "
                                "Compare the primary motif with alternate binding modes.",
                            ),
                            (
                                "Protein–DNA structure",
                                "Where available, inspect the predicted complex and "
                                "isolate its DNA-binding domains or highlight DNA contacts.",
                            ),
                            (
                                "Support and references",
                                "Review cluster support and structural confidence. "
                                "Where an ortholog motif is available, compare the "
                                "prediction with JASPAR.",
                            ),
                        ]
                    ],
                    className="search-empty-guide",
                ),
                html.P(
                    "Some TFs share predictions with a modeled representative. "
                    "Results identify which protein the motifs and structure describe.",
                    className="search-empty-note",
                ),
                html.Div(
                    [
                        dcc.Link("How predictions are made →", href="/methods"),
                        dcc.Link("Download motif matrices →", href="/downloads")
                        if DOWNLOADS_ENABLED
                        else None,
                    ],
                    className="search-empty-links",
                ),
            ],
            id="search-empty-state",
            className="container search-empty-state",
            **{"aria-labelledby": "search-empty-heading"},
        ),
        html.Section(
            [
                html.Div(id="tf-result-note", className="tf-result-note"),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Header(
                                    [
                                        html.Div(
                                            [
                                                html.Div(id="tf-result-identity"),
                                            ],
                                            className="tf-result-details",
                                        ),
                                    ],
                                    id="tf-result-header",
                                    className="tf-result-header",
                                    **{"aria-labelledby": "tf-result-name"},
                                ),
                                html.Div(
                                    id="overview-section",
                                    style={"display": "none"},
                                    children=[html.Div(id="overview-content")],
                                ),
                                html.Div(id="primary-validation"),
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                dbc.Button(
                                                    "Copy link",
                                                    id="copy-tf-link",
                                                    n_clicks=0,
                                                    color="primary",
                                                    outline=True,
                                                    disabled=True,
                                                ),
                                                dbc.Button(
                                                    "Download this TF's motifs (.meme)",
                                                    id="download-tf-motifs",
                                                    color="primary",
                                                    external_link=True,
                                                    disabled=True,
                                                    title="Download the primary and all available alternate motifs",
                                                    style=None
                                                    if DOWNLOADS_ENABLED
                                                    else {"display": "none"},
                                                ),
                                            ],
                                            className="tf-result-buttons",
                                        ),
                                        html.Div(
                                            id="copy-tf-link-status",
                                            className="tf-link-status",
                                            role="status",
                                            **{"aria-live": "polite"},
                                        ),
                                        html.Div(
                                            [
                                                html.Label(
                                                    "Shareable link",
                                                    htmlFor="tf-share-url",
                                                ),
                                                dcc.Input(
                                                    id="tf-share-url",
                                                    type="text",
                                                    value="",
                                                    readOnly=True,
                                                    className="form-control",
                                                ),
                                            ],
                                            id="tf-share-fallback",
                                            className="tf-share-fallback",
                                            style={"display": "none"},
                                        ),
                                    ],
                                    className="tf-result-actions",
                                ),
                            ],
                            md=4,
                            className="profile-col",
                        ),
                        dbc.Col(
                            html.Div(
                                id="primary-section",
                                style={"display": "none"},
                                children=[
                                    html.H4(
                                        "Primary binding mode",
                                        style={
                                            "color": "var(--heading)",
                                            "marginBottom": "6px",
                                        },
                                    ),
                                    dcc.Markdown(
                                        "The primary mode is the consensus of the largest cluster "
                                        "of predicted specificities: the most supported predicted "
                                        "binding mode.",
                                        style={
                                            "color": "var(--text-muted)",
                                            "fontSize": "0.9em",
                                        },
                                    ),
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    html.Span("Logo scale"),
                                                    dbc.RadioItems(
                                                        id="motif-logo-scale",
                                                        options=[
                                                            {
                                                                "label": "IC",
                                                                "value": "ic",
                                                            },
                                                            {
                                                                "label": "Log-odds",
                                                                "value": "log_odds",
                                                            },
                                                        ],
                                                        value="ic",
                                                        className="motif-scale-options",
                                                        inputClassName="btn-check",
                                                        labelClassName="btn btn-outline-primary btn-sm",
                                                        labelCheckedClassName="active",
                                                    ),
                                                ],
                                                className="motif-scale-control",
                                                role="group",
                                                **{
                                                    "aria-label": "Logo scale for all motifs"
                                                },
                                            ),
                                            dbc.Switch(
                                                id="motif-reverse-complement",
                                                label="Reverse complement all motifs",
                                                value=False,
                                                className="motif-orientation-control",
                                            ),
                                        ],
                                        className="motif-display-controls",
                                    ),
                                    dcc.Graph(
                                        id="primary-logo",
                                        config={"displayModeBar": False},
                                    ),
                                ],
                            ),
                            md=8,
                        ),
                    ],
                    className="mode-row tf-result-row",
                    align="stretch",
                ),
            ],
            id="tf-result-panel",
            className="container tf-result-panel",
            style={"display": "none"},
            **{"aria-labelledby": "tf-result-name"},
        ),
        # Alternate modes span the page directly below the primary mode.
        dbc.Row(
            dbc.Col(
                html.Div(
                    id="alternate-section",
                    className="container",
                    style={"display": "none"},
                    children=[
                        html.H4(
                            "Alternate binding modes",
                            style={
                                "color": "var(--heading)",
                                "fontSize": "1.2rem",
                                "marginBottom": "4px",
                            },
                        ),
                        dcc.Markdown(
                            "Additional consensus motifs from smaller clusters, aligned "
                            "to the primary's orientation and positions. Blank flanks "
                            "fall outside that motif; positions outside the primary "
                            "show overhanging bases.",
                            className="alternate-modes-description",
                            style={
                                "color": "var(--text-muted)",
                                "fontSize": "0.8rem",
                            },
                        ),
                        html.Div(
                            id="alternate-content", className="alternate-modes-grid"
                        ),
                    ],
                ),
                width=12,
            )
        ),
        # Structure and protein-level confidence share a card, stacking on small screens.
        dbc.Row(
            dbc.Col(
                html.Div(
                    [
                        html.Section(
                            id="structure-section",
                            className="structure-panel",
                            style={"display": "none"},
                            **{"aria-labelledby": "structure-heading"},
                            children=[
                                html.Div(
                                    [
                                        html.H4(
                                            "Predicted structure",
                                            id="structure-heading",
                                            style={
                                                "color": "var(--heading)",
                                                "marginBottom": 0,
                                            },
                                        ),
                                        html.Button(
                                            "Expand viewer",
                                            id="expand-structure-viewer",
                                            type="button",
                                            className="btn btn-outline-primary btn-sm",
                                            **{
                                                "aria-expanded": "false",
                                                "aria-controls": "structure-content",
                                            },
                                        ),
                                    ],
                                    className="structure-panel-header",
                                ),
                                dcc.Markdown(
                                    "The displayed AlphaFold 3 structure is the highest-ranked "
                                    "member of the primary binding mode. Drag to rotate; scroll to zoom.",
                                    className="structure-description panel-description",
                                ),
                                # Domain/contact controls require the corresponding annotation.
                                html.Div(
                                    style={
                                        "display": "flex",
                                        "flexWrap": "wrap",
                                        "columnGap": "24px",
                                        "alignItems": "center",
                                    },
                                    children=[
                                        # Shown only when the rep has a DNA-binding-domain annotation.
                                        html.Div(
                                            id="dbd-toggle-row",
                                            style={
                                                "display": "none",
                                                "marginBottom": "8px",
                                            },
                                            children=dbc.Checklist(
                                                id="dbd-toggle",
                                                options=[
                                                    {
                                                        "label": "Show only DNA-binding domain",
                                                        "value": "on",
                                                    }
                                                ],
                                                value=[],
                                                switch=True,
                                            ),
                                        ),
                                        # Shown only when the rep has DNA-contact residues annotated.
                                        html.Div(
                                            id="contacts-toggle-row",
                                            style={
                                                "display": "none",
                                                "marginBottom": "8px",
                                            },
                                            children=dbc.Checklist(
                                                id="contacts-toggle",
                                                options=[
                                                    {
                                                        "label": "Show DNA contacts",
                                                        "value": "on",
                                                    }
                                                ],
                                                value=[],
                                                switch=True,
                                            ),
                                        ),
                                    ],
                                ),
                                html.Div(
                                    id="plddt-legend",
                                    className="structure-color-legend",
                                    style={"display": "none"},
                                    role="note",
                                    **{"aria-label": "pLDDT color key"},
                                ),
                                # Color key for the DNA-contacts view (populated by the callback).
                                html.Div(
                                    id="contacts-legend", style={"display": "none"}
                                ),
                                html.P(
                                    id="domain-status",
                                    className="confidence-scope",
                                    style={"display": "none"},
                                ),
                                # The viewer is rebuilt by the callback on each selection so
                                # it mounts into an already-visible, sized container; a
                                # MolstarViewer created while its parent is display:none
                                # initializes its WebGL canvas at 0×0 and never resizes when
                                # the section is later revealed.
                                html.Div(id="structure-content"),
                            ],
                        ),
                        html.Section(
                            id="confidence-section",
                            className="confidence-panel",
                            style={"display": "none"},
                            **{"aria-labelledby": "confidence-heading"},
                            children=[
                                html.H4(
                                    "AF3 confidence",
                                    id="confidence-heading",
                                    style={"marginBottom": "6px"},
                                ),
                                dcc.Markdown(
                                    "Confidence in the predicted DNA-binding domain "
                                    "and protein–DNA interface.",
                                    className="confidence-description panel-description",
                                ),
                                html.Div(id="confidence-content"),
                            ],
                        ),
                    ],
                    id="structure-confidence-section",
                    className="container structure-confidence-card",
                ),
                width=12,
            ),
        ),
    ],
)


def sync_search_link(dbid, search, pathname, initialized):
    """Load shared links once, then distinguish navigation from dropdown changes."""
    if pathname != "/search":
        raise PreventUpdate
    navigation = synchronize_tf_search(
        dbid,
        search,
        catalog.TF2REP_BY_DBID.index,
        from_url=not initialized or "search-url.search" in ctx.triggered_prop_ids,
    )
    return (
        dash.no_update if navigation.dbid == dbid else navigation.dbid,
        dash.no_update if navigation.search == (search or "") else navigation.search,
        True,
        navigation.message,
    )


def _fmt(value, *, percent=False, decimal_places=None, dash="—"):
    """Format a possibly-null numeric value for display."""
    return format_number(
        value, percent=percent, decimal_places=decimal_places, missing=dash
    )


def _kv_table(items) -> html.Table:
    """A two-column key/value table (the JASPAR-style profile body)."""
    return html.Table(
        html.Tbody(
            [
                html.Tr(
                    [
                        html.Td(k, className="profile-key"),
                        html.Td(v, className="profile-val"),
                    ]
                )
                for k, v in items
            ]
        ),
        className="profile-table",
    )


def _profile_panel(items, title=None, badge=None) -> html.Div:
    """Vertical JASPAR-style profile: optional badge/title, then a key/value table."""
    head = []
    if badge is not None:
        head.append(html.Div(badge, className="profile-badge"))
    if title is not None:
        head.append(html.Div(title, className="profile-title"))
    return html.Div(head + [_kv_table(items)], className="profile-panel")


def _metric_badge(row: pd.Series, metric: str):
    """Show the exported band and value, with full details on hover or keyboard focus."""
    missing = "Unavailable" if metric == "support" else "No reference"
    label = row.get(f"{metric}_band", missing)
    if pd.isna(label):
        label = missing
    color = {"Low": "secondary", "Medium": "warning", "High": "success"}.get(
        label, "secondary"
    )
    value = None
    if metric == "support":
        title = "Support"
        if label == "Unavailable":
            detail = "Prediction support is unavailable."
        else:
            members, total = int(row["n_members"]), int(row["num_specs"])
            detail = (
                f"{members} of {total} predictions support this mode "
                f"({_fmt(members / total, percent=True)})."
            )
            percentage = _fmt(members / total, percent=True, decimal_places=0)
            value = f"{members}/{total} ({percentage})"
    elif metric == "homer_sim":
        title = "Motif similarity"
        if label == "No reference":
            detail = "No reference motif comparison is available."
        else:
            p = row.get("p_value")
            p_value = _fmt(p)
            # Preserve small empirical p-values rather than rounding them to zero.
            if pd.notna(p) and 0 < p < 0.001:
                p_value = f"{p:.2g}"
            detail = (
                f"HOMER similarity: {_fmt(row.get('homer_sim'))}; "
                f"empirical p-value: {p_value}."
            )
            value = f"HOMER {_fmt(row.get('homer_sim'), decimal_places=2)}, p={p_value}"
    elif metric == "recovery":
        title = "IC recovery"
        if label == "No reference":
            detail = "No reference motif comparison is available."
        else:
            recovery = row.get("recovery")
            raw_recovery = _fmt(recovery)
            percentage = _fmt(recovery, percent=True)
            value = _fmt(recovery, percent=True, decimal_places=0)
            if pd.notna(recovery) and 0 < recovery < 0.01:
                raw_recovery = f"{recovery:.2g}"
                value = f"{recovery * 100:.2g}%"
                percentage = value
            detail = f"IC recovery: {raw_recovery} ({percentage})."
    else:
        raise ValueError(f"No display band defined for {metric}")
    motif = str(row["motif_id"]).replace(".", "-")
    target = f"metric-band-{motif}-{metric.replace('_', '-')}"
    return html.Span(
        [
            html.Span(
                [
                    dbc.Badge(
                        label,
                        color=color,
                        text_color="dark" if color == "warning" else "white",
                        className="metric-band",
                    ),
                    html.Span(value, className="metric-value")
                    if value is not None
                    else None,
                ],
                id=target,
                className="metric-band-trigger",
                tabIndex=0,
                **{"aria-label": f"{title}: {label}. {detail}"},
            ),
            dbc.Tooltip(
                detail,
                id=f"{target}-tooltip",
                target=target,
                trigger="hover focus",
                placement="top",
                delay={"show": 100, "hide": 0},
                class_name="metric-value-tooltip",
            ),
        ],
        className="metric-reading",
    )


def _validation_rows(row: pd.Series):
    """JASPAR reference comparisons, or None if the mode has no ortholog."""
    jaspar = row.get("hom_jaspar")
    if jaspar is None or (isinstance(jaspar, float) and pd.isna(jaspar)):
        return None
    similarity = _fmt(row.get("hom_sim"), decimal_places=0, dash="")
    return [
        (
            "JASPAR ortholog",
            html.Span(
                [
                    html.A(
                        str(jaspar),
                        href=f"https://jaspar.elixir.no/matrix/{jaspar}/",
                        target="_blank",
                        rel="noopener noreferrer",
                    ),
                    f" ({similarity}% DBD similarity)" if similarity else "",
                ]
            ),
        ),
        (
            "Motif similarity",
            _metric_badge(row, "homer_sim"),
        ),
        ("IC recovery", _metric_badge(row, "recovery")),
    ]


def _zfin_cell(dbid):
    """Linked ZFIN gene ID for this DBID, or a faint dash if there's no 1:1 mapping."""
    zfin_id = catalog.ZFIN_BY_DBID.get(dbid)
    if zfin_id is None:
        return html.Span("—", style={"color": "var(--text-faint)"})
    return html.A(
        zfin_id,
        href=f"https://zfin.org/{zfin_id}",
        target="_blank",
        rel="noopener noreferrer",
    )


def _confidence_level(metric, value):
    """Interpret a median score using the usual pLDDT / ipTM confidence bands.

    A zero domain pLDDT is the upstream sentinel for an unannotated DNA-binding
    domain, so it is unavailable rather than a low-confidence prediction.
    """
    if value is None or not np.isfinite(value):
        return None
    if metric == "dom_pLDDT":
        if value <= 0:
            return None
        if value >= 90:
            return "Very high", f"#{structure_viewer.PLDDT_COLORS[0][1]:06X}"
        if value >= 70:
            return "High", f"#{structure_viewer.PLDDT_COLORS[1][1]:06X}"
        if value >= 50:
            return "Low", f"#{structure_viewer.PLDDT_COLORS[2][1]:06X}"
        return "Very low", f"#{structure_viewer.PLDDT_COLORS[3][1]:06X}"
    if metric == "ipTM":
        if value > 0.8:
            return "High", "success"
        if value >= 0.6:
            return "Uncertain", "warning"
        return "Low", "secondary"
    raise ValueError(f"No confidence bands defined for {metric}")


def _confidence_metric(metric, title, row, unavailable_reason=None):
    """A median score and 10th–90th percentile range across selected predictions."""
    level = (
        None
        if row is None or unavailable_reason is not None
        else _confidence_level(metric, row.get("p50"))
    )
    if level is None:
        return html.Div(
            [
                html.Div(title, className="confidence-metric-title"),
                html.Div("Unavailable", className="confidence-score"),
                html.Div(
                    unavailable_reason
                    or (
                        "No domain confidence estimate was computed."
                        if metric == "dom_pLDDT" and row is not None
                        else "No confidence estimate is available."
                    ),
                    className="confidence-range",
                ),
            ],
            className="confidence-metric",
        )
    label, color = level
    unit = "/100 pLDDT" if metric == "dom_pLDDT" else "ipTM"
    decimal_places = 1 if metric == "dom_pLDDT" else None
    return html.Div(
        [
            html.Div(
                [
                    html.Span(title),
                    dbc.Badge(
                        label,
                        color=color,
                        text_color=(
                            "dark"
                            if color == "warning"
                            or (metric == "dom_pLDDT" and label != "Very high")
                            else "white"
                        ),
                    ),
                ],
                className="confidence-metric-title",
            ),
            html.Div(
                [
                    html.Span(_fmt(row["p50"], decimal_places=decimal_places)),
                    html.Span(f" {unit}", className="confidence-unit"),
                ],
                className="confidence-score",
            ),
            html.Div(
                f"Middle 80%: {_fmt(row.get('p10'), decimal_places=decimal_places)}–"
                f"{_fmt(row.get('p90'), decimal_places=decimal_places)} "
                f"· {int(row['n'])} predictions",
                className="confidence-range",
            ),
        ],
        className="confidence-metric",
    )


def _confidence_summary(rep, tf_name):
    """Shared protein-level confidence, with variability and explicit missing data."""
    tf_name = display_tf_name(tf_name)
    metrics = catalog.CONFIDENCE_BY_DBID.get(rep)
    if not metrics:
        return html.P(
            f"A confidence summary is not available for {tf_name}.",
            className="confidence-scope",
        )
    definitions = [
        ("dom_pLDDT", "DNA-binding domain"),
        ("ipTM", "Protein–DNA interface"),
    ]
    domain_message = catalog.DOMAIN_STATUS_BY_DBID.get(rep)
    variation = []
    for metric, title in definitions:
        if metric == "dom_pLDDT" and domain_message is not None:
            continue
        row = metrics.get(metric)
        level = None if row is None else _confidence_level(metric, row.get("p50"))
        if level is None:
            continue
        low = _confidence_level(metric, row.get("p10"))
        high = _confidence_level(metric, row.get("p90"))
        # Require a visible spread as well as a band crossing for a variation note.
        min_width = 5.0 if metric == "dom_pLDDT" else 0.1
        if (
            low
            and high
            and low[0] != high[0]
            and round(row["p90"] - row["p10"], 4) >= min_width
        ):
            variation.append(
                f"{title} confidence varies from {low[0].lower()} to "
                f"{high[0].lower()} across the middle 80% of predictions."
            )
    children = [
        html.P(
            "Scores summarize the selected top-ranked predictions across binding modes.",
            className="confidence-scope",
        )
    ]
    children.append(
        html.Div(
            [
                _confidence_metric(
                    metric,
                    title,
                    metrics.get(metric),
                    unavailable_reason=domain_message
                    if metric == "dom_pLDDT"
                    else None,
                )
                for metric, title in definitions
            ],
            className="confidence-metrics",
        )
    )
    if variation:
        children.append(html.P(" ".join(variation), className="confidence-variation"))
    help_content = [
        html.Summary("How to read these scores"),
        html.P(
            "Domain pLDDT estimates local structural confidence in the DNA-binding "
            "domain. ipTM estimates confidence in the protein–DNA placement. "
            "Higher scores indicate greater confidence. Labels describe the median; "
            "the middle 80% range spans the 10th–90th percentiles across predictions.",
        ),
    ]
    protein = metrics.get("prot_pTM")
    if protein is not None and np.isfinite(protein.get("p50", np.nan)):
        help_content.append(
            html.P(
                "Protein fold pTM: "
                f"{_fmt(protein['p50'])} (middle 80%: {_fmt(protein['p10'])}–"
                f"{_fmt(protein['p90'])}). This score describes the global protein "
                "fold, while domain pLDDT describes local confidence.",
            )
        )
    help_content.append(
        html.P(
            [
                "Score interpretation: ",
                html.A(
                    "AlphaFold 3 confidence metrics",
                    href="https://github.com/google-deepmind/alphafold3/blob/main/docs/output.md#confidence-metrics",
                    target="_blank",
                    rel="noopener noreferrer",
                ),
                " · ",
                html.A(
                    "pLDDT guide",
                    href="https://www.ebi.ac.uk/training/online/courses/alphafold/inputs-and-outputs/evaluating-alphafolds-predicted-structures-using-confidence-scores/plddt-understanding-local-confidence/",
                    target="_blank",
                    rel="noopener noreferrer",
                ),
            ]
        )
    )
    children.append(html.Details(help_content, className="confidence-help"))
    return html.Div(children)


def _tf_identity(sel: pd.Series, dbid) -> html.Div:
    """Selected TF identity; domain entries link to their parent Ensembl gene."""
    representative = sel.get("Rep_DBID")
    shared_prediction = pd.notna(representative) and representative != dbid
    identifiers = [
        (
            "Ensembl ID",
            html.A(
                base_gene_dbid(dbid),
                href=(
                    "https://useast.ensembl.org/Danio_rerio/Gene/Summary?db=core;"
                    f"g={base_gene_dbid(dbid)}"
                ),
                target="_blank",
                rel="noopener noreferrer",
            ),
        ),
        ("ZFIN ID", _zfin_cell(dbid)),
    ]
    if base_gene_dbid(dbid) != dbid:
        identifiers.append(("Query ID", html.Code(dbid)))
    return html.Div(
        [
            html.P("Selected TF", className="tf-result-query-label")
            if shared_prediction
            else None,
            html.H2(display_tf_name(sel["TF_Name"]), id="tf-result-name"),
            html.P(["Family: ", sel["Family"]], className="tf-result-family"),
            html.Dl(
                [
                    html.Div([html.Dt(label), html.Dd(value)])
                    for label, value in identifiers
                ],
                className="tf-result-identifiers",
                **{"aria-label": "Selected TF identifiers"},
            ),
        ]
    )


def _motif_id_link(motif_id: str, **attributes):
    """Link a PPM ID to its MEME file, or show plain text while downloads are off."""
    if not DOWNLOADS_ENABLED:
        return motif_id
    return html.A(
        motif_id,
        href=f"/motifs/{motif_id}.txt",
        target="_blank",
        rel="noopener noreferrer",
        **attributes,
    )


def _primary_profile(primary: pd.Series) -> html.Div:
    """Primary motif identifier, support, and JASPAR comparisons."""
    identity = [
        (
            "PPM ID",
            _motif_id_link(primary["motif_id"]),
        ),
    ]

    val_items = _validation_rows(primary)
    if val_items is None:
        val_items = [
            (
                "JASPAR ortholog",
                html.Span("—", style={"color": "var(--text-faint)"}),
            ),
            ("Motif similarity", _metric_badge(primary, "homer_sim")),
            ("IC recovery", _metric_badge(primary, "recovery")),
        ]
    identity += [
        val_items[0],
        ("Support", _metric_badge(primary, "support")),
        *val_items[1:],
    ]

    return _profile_panel(identity)


def _mode_profile(row: pd.Series) -> html.Div:
    """Linked alternate PPM ID, metric bands, and visible numeric values."""
    items = [
        (
            "PPM ID",
            _motif_id_link(row["motif_id"], title="Open MEME motif file"),
        ),
        ("Support", _metric_badge(row, "support")),
        ("Motif similarity", _metric_badge(row, "homer_sim")),
        ("IC recovery", _metric_badge(row, "recovery")),
    ]
    return html.Div(
        [
            html.Span(
                [html.Span(f"{key}: ", className="mode-meta-key"), html.B(value)],
                className="mode-meta-item",
            )
            for key, value in items
        ],
        className="mode-meta",
    )


def _representative_notice(selected, primary):
    """Identify the modeled protein supplying every prediction in a shared result."""
    name = display_tf_name(primary["TF_Name"])
    query_name = display_tf_name(selected["TF_Name"])
    link = f"/search?tf={primary['DBID']}"
    label = {
        "cluster": "Sequence-cluster representative",
        "symbol_redirect": "Gene-symbol redirect",
    }.get(selected["resolution"], "Modeled representative")
    return html.Div(
        [
            html.Div(
                [
                    html.P(
                        [
                            "Showing predictions for ",
                            dcc.Link(html.Strong(name), href=link),
                        ],
                        id="tf-representative-title",
                        className="tf-representative-title",
                    ),
                    html.Span(label, className="tf-representative-label"),
                ],
                className="tf-representative-heading",
            ),
            html.P(
                [
                    "You selected ",
                    html.Strong(query_name),
                    ". The motifs, JASPAR comparisons, structure, and confidence below are for ",
                    html.Strong(name),
                    ".",
                ],
                className="tf-representative-description",
            ),
            html.P(
                ["Modeled entry: ", dcc.Link(primary["DBID"], href=link)],
                className="tf-representative-entry",
            ),
        ],
        className="tf-representative-notice",
        role="note",
        **{"aria-labelledby": "tf-representative-title"},
    )


def update_result_header(dbid):
    """Keep query identity and actions separate from the representative's motifs."""
    if not isinstance(dbid, str) or dbid not in catalog.TF2REP_BY_DBID.index:
        return {
            "tf_result_panel_style": {"display": "none"},
            "tf_result_identity": None,
            "tf_result_note": None,
            "copy_tf_link_disabled": True,
            "download_tf_motifs_href": None,
            "download_tf_motifs_disabled": True,
        }
    sel = catalog.TF2REP_BY_DBID.loc[dbid]
    modes = catalog.modes_for_query(dbid)
    note = None
    if modes is not None:
        primary = modes.iloc[0]
        if primary["DBID"] != dbid:
            note = _representative_notice(sel, primary)
    return {
        "tf_result_panel_style": {},
        "tf_result_identity": _tf_identity(sel, dbid),
        "tf_result_note": note,
        "copy_tf_link_disabled": False,
        "download_tf_motifs_href": f"/motifs/tf/{dbid}.meme"
        if modes is not None and DOWNLOADS_ENABLED
        else None,
        "download_tf_motifs_disabled": modes is None or not DOWNLOADS_ENABLED,
    }


def update_confidence(dbid):
    """Resolve the query to the protein whose structures and confidence are shown."""
    hidden = {
        "confidence_section_style": {"display": "none"},
        "confidence_content": None,
    }
    if not dbid:
        return hidden
    rep = catalog.TF2REP_BY_DBID.loc[dbid, "Rep_DBID"]
    if pd.isna(rep) or rep not in catalog.MODES_BY_DBID:
        return hidden
    primary = catalog.MODES_BY_DBID[rep]
    primary = primary[primary["tier"] == "primary"].iloc[0]
    return {
        "confidence_section_style": {},
        "confidence_content": _confidence_summary(rep, primary["TF_Name"]),
    }


def update_tf(dbid, reverse=False, scale="ic"):
    """Resolve the selected TF and render its primary logo (with profile) and alternate modes."""
    hidden = {"display": "none"}
    shown = {}

    if not dbid:
        return {
            "overview_content": None,
            "overview_section_style": hidden,
            "primary_section_style": hidden,
            "primary_validation": None,
            "primary_logo": {},
            "alternate_section_style": hidden,
            "alternate_content": None,
            "search_empty_state_style": shown,
        }

    sel = catalog.TF2REP_BY_DBID.loc[dbid]
    rep = sel["Rep_DBID"]

    # Query identity stays in the header even when no predicted PPM is available.
    if (
        rep is None
        or (isinstance(rep, float) and pd.isna(rep))
        or rep not in catalog.MODES_BY_DBID
    ):
        return {
            "overview_content": html.P(
                "No predicted PPM is available for this transcription factor.",
                className="mb-0",
            ),
            "overview_section_style": shown,
            "primary_section_style": hidden,
            "primary_validation": None,
            "primary_logo": {},
            "alternate_section_style": hidden,
            "alternate_content": None,
            "search_empty_state_style": hidden,
        }

    modes = catalog.MODES_BY_DBID[rep]
    primary = modes[modes["tier"] == "primary"].iloc[0]
    alternates = modes[modes["tier"] == "alternate"]

    primary_ppm = as_pwm(primary["pwm"])
    primary_length = len(primary_ppm)
    placed = [(primary_ppm, 0)]
    for _, row in alternates.iterrows():
        ppm = as_pwm(row["pwm"])
        if row["rc_to_primary"]:
            ppm = reverse_complement(ppm)
        # The exporter defines positive offsets as alternate bases shifted right.
        placed.append((ppm, int(row["offset_to_primary"])))
    if reverse:
        placed = [
            (reverse_complement(ppm), primary_length - offset - len(ppm))
            for ppm, offset in placed
        ]
    position_range = (
        min(offset for _, offset in placed),
        max(offset + len(ppm) for ppm, offset in placed),
    )

    # ── Primary logo + profile (identity + validation) ───────────────────────
    primary_fig = plot_logo(
        placed[0][0],
        height=300,
        position_range=position_range,
        show_reverse_complement=False,
        scale=scale,
    )
    primary_fig.update_layout(xaxis_title="Position")
    primary_validation = _primary_profile(primary)

    # ── Alternate modes ──────────────────────────────────────────────────────
    if len(alternates) == 0:
        alt_style = hidden
        alt_children = None
    else:
        alt_style = shown
        cards = []
        for i, (_, row) in enumerate(alternates.iterrows()):
            ppm, offset = placed[i + 1]
            fig = plot_logo(
                ppm,
                height=160,
                position_offset=offset,
                position_range=position_range,
                show_reverse_complement=False,
                scale=scale,
            )
            fig.update_layout(
                margin={"l": 42, "r": 12, "t": 30, "b": 38},
                font={"size": 11},
                xaxis={
                    "title": {
                        "text": "Position relative to primary",
                        "font": {"size": 11},
                    },
                    "tickfont": {"size": 10},
                },
                yaxis={
                    "title": {
                        "text": "IC (bits)" if scale == "ic" else "Log₂(p/0.25)",
                        "font": {"size": 11},
                    },
                    "tickfont": {"size": 10},
                    "tickmode": "array",
                    "tickvals": [0, 1, 2],
                },
            )
            # Each alternate keeps its metrics above its logo in the horizontal grid.
            cards.append(
                html.Div(
                    [
                        html.H5(f"Alternate {i + 1}", className="profile-title"),
                        _mode_profile(row),
                        html.Div(
                            [
                                dcc.Graph(
                                    figure=fig,
                                    config={"displayModeBar": False},
                                    id={"type": "alt-logo", "index": i},
                                    className="alternate-mode-logo",
                                ),
                            ],
                            className="alternate-mode-plot",
                        ),
                    ],
                    className="alternate-mode-card",
                )
            )
        alt_children = cards

    return {
        "overview_content": None,
        "overview_section_style": hidden,
        "primary_section_style": shown,
        "primary_validation": primary_validation,
        "primary_logo": primary_fig,
        "alternate_section_style": alt_style,
        "alternate_content": alt_children,
        "search_empty_state_style": hidden,
    }


def update_structure(dbid, dbd_toggle, contacts_toggle):
    """Render confidence or contacts colors, with optional domain filtering.

    Runs on TF change and on toggling any structure switch. The viewer is (re)built here rather
    than persisted so it mounts into an already-visible, sized container.
    """
    hidden = {"display": "none"}
    toggle_hidden = {"display": "none", "marginBottom": "8px"}
    toggle_shown = {"marginBottom": "8px"}
    legend_hidden = {"display": "none"}
    legend_shown = {
        "display": "flex",
        "flexWrap": "wrap",
        "fontSize": "0.85em",
        "color": "var(--text-muted)",
        "marginBottom": "8px",
    }
    off = {
        "structure_section_style": hidden,
        "structure_content": None,
        "dbd_toggle_row_style": toggle_hidden,
        "contacts_toggle_row_style": toggle_hidden,
        "contacts_legend": None,
        "contacts_legend_style": legend_hidden,
        "plddt_legend": None,
        "plddt_legend_style": legend_hidden,
        "domain_status": None,
        "domain_status_style": hidden,
    }

    if not dbid:
        return off

    sel = catalog.TF2REP_BY_DBID.loc[dbid]
    rep = sel["Rep_DBID"]
    if (
        rep is None
        or (isinstance(rep, float) and pd.isna(rep))
        or rep not in catalog.MODES_BY_DBID
    ):
        return off

    primary = catalog.MODES_BY_DBID[rep]
    primary = primary[primary["tier"] == "primary"].iloc[0]

    dbd = catalog.DBD_BY_DBID.get(rep)
    domain_message = catalog.DOMAIN_STATUS_BY_DBID.get(rep)
    domains_only = dbd if (dbd and "on" in (dbd_toggle or [])) else None

    contacts_map = catalog.CONTACTS_BY_DBID.get(rep)
    show_contacts = bool(contacts_map) and "on" in (contacts_toggle or [])
    contacts = contacts_map if show_contacts else None
    if contacts and domains_only:
        contacts = {
            r: mode
            for r, mode in contacts.items()
            if any(start <= r <= end for start, end, _ in domains_only)
        }
    data = structure_viewer.structure_data(
        primary.get("structure_path"), dbd=domains_only, contacts=contacts
    )
    if data is None:
        return off

    viewer = dash_molstar.MolstarViewer(
        data=data,
        focus=structure_viewer.structure_focus(primary["structure_path"], dbd),
        layout=structure_viewer.VIEWER_LAYOUT,
        # The surrounding viewport controls normal and expanded sizes without remounting.
        style={"width": "100%", "height": "100%", "position": "relative"},
    )
    # Show the key for the active color scheme; annotation toggles require annotations.
    return {
        "structure_section_style": {},
        "structure_content": viewer,
        "dbd_toggle_row_style": toggle_shown if dbd else toggle_hidden,
        "contacts_toggle_row_style": toggle_shown if contacts_map else toggle_hidden,
        "contacts_legend": structure_viewer.build_contacts_legend(contacts)
        if show_contacts
        else None,
        "contacts_legend_style": legend_shown if show_contacts else legend_hidden,
        "plddt_legend": None
        if show_contacts
        else structure_viewer.build_plddt_legend(),
        "plddt_legend_style": legend_hidden if show_contacts else {},
        "domain_status": domain_message,
        "domain_status_style": {} if domain_message is not None else hidden,
    }


# Named fields keep helper results aligned with their Dash component outputs.
RESULT_OUTPUTS = {
    "tf_result_panel_style": Output("tf-result-panel", "style"),
    "tf_result_identity": Output("tf-result-identity", "children"),
    "tf_result_note": Output("tf-result-note", "children"),
    "copy_tf_link_disabled": Output("copy-tf-link", "disabled"),
    "download_tf_motifs_href": Output("download-tf-motifs", "href"),
    "download_tf_motifs_disabled": Output("download-tf-motifs", "disabled"),
    "confidence_section_style": Output("confidence-section", "style"),
    "confidence_content": Output("confidence-content", "children"),
    "overview_content": Output("overview-content", "children"),
    "overview_section_style": Output("overview-section", "style"),
    "primary_section_style": Output("primary-section", "style"),
    "primary_validation": Output("primary-validation", "children"),
    "primary_logo": Output("primary-logo", "figure"),
    "alternate_section_style": Output("alternate-section", "style"),
    "alternate_content": Output("alternate-content", "children"),
    "search_empty_state_style": Output("search-empty-state", "style"),
    "structure_section_style": Output("structure-section", "style"),
    "structure_content": Output("structure-content", "children"),
    "dbd_toggle_row_style": Output("dbd-toggle-row", "style"),
    "contacts_toggle_row_style": Output("contacts-toggle-row", "style"),
    "contacts_legend": Output("contacts-legend", "children"),
    "contacts_legend_style": Output("contacts-legend", "style"),
    "plddt_legend": Output("plddt-legend", "children"),
    "plddt_legend_style": Output("plddt-legend", "style"),
    "domain_status": Output("domain-status", "children"),
    "domain_status_style": Output("domain-status", "style"),
    "search_result_selection": Output("search-result-selection", "data"),
}


def update_search_result(
    dbid, reverse, scale, dbd_toggle, contacts_toggle, rendered_dbid
):
    """Replace the empty state or previous TF with one complete selection response.

    Independent tile callbacks can expose a structure before its matching motif and
    identity arrive. Commit all selection outputs together; display controls only
    rebuild the affected figures so the structure keeps its camera on logo changes.
    """
    if not isinstance(dbid, str) or dbid not in catalog.TF2REP_BY_DBID.index:
        dbid = None

    changed = set(ctx.triggered_prop_ids)
    result = dict.fromkeys(RESULT_OUTPUTS, dash.no_update)
    # A switch can supersede a pending selection request. Until that TF is committed,
    # its switch response must also include the complete selection.
    if (
        dbid == rendered_dbid
        and changed
        and changed
        <= {
            "motif-reverse-complement.value",
            "motif-logo-scale.value",
        }
    ):
        result.update(update_tf(dbid, reverse, scale))
        return result
    if (
        dbid == rendered_dbid
        and changed
        and changed
        <= {
            "dbd-toggle.value",
            "contacts-toggle.value",
        }
    ):
        result.update(update_structure(dbid, dbd_toggle, contacts_toggle))
        return result

    result.update(update_result_header(dbid))
    result.update(update_confidence(dbid))
    result.update(update_tf(dbid, reverse, scale))
    result.update(update_structure(dbid, dbd_toggle, contacts_toggle))
    result["search_result_selection"] = dbid
    return result


def register_callbacks(app):
    """Register this page's callbacks on the shared Dash app."""
    app.callback(
        Output("tf-dropdown", "value"),
        Output("url", "search"),
        Output("search-link-state", "data"),
        Output("search-link-message", "children"),
        Input("tf-dropdown", "value"),
        Input("search-url", "search"),
        State("url", "pathname"),
        State("search-link-state", "data"),
    )(sync_search_link)

    app.clientside_callback(
        dash.ClientsideFunction(namespace="tfResultHeader", function_name="copyLink"),
        Output("copy-tf-link-status", "children"),
        Output("tf-share-fallback", "style"),
        Output("tf-share-url", "value"),
        Input("copy-tf-link", "n_clicks"),
        Input("tf-dropdown", "value"),
    )

    app.callback(
        output=RESULT_OUTPUTS,
        inputs=[
            Input("tf-dropdown", "value"),
            Input("motif-reverse-complement", "value"),
            Input("motif-logo-scale", "value"),
            Input("dbd-toggle", "value"),
            Input("contacts-toggle", "value"),
        ],
        state=[State("search-result-selection", "data")],
    )(update_search_result)
