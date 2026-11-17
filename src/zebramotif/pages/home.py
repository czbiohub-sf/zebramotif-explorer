"""Home page with catalog statistics, TF search, and a static irf2 example.

Keep the example images in sync with the installed release.
"""

import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate

from zebramotif import data as catalog
from zebramotif.downloads import DOWNLOADS_ENABLED

HOME_EXAMPLE_DBID = "ENSDARG00000040465"  # irf2

HOME_STATS = [
    (f"{catalog.N_TFS:,}", "Zebrafish TF genes in the catalog"),
    (f"{catalog.N_MODELED_SEQUENCES:,}", "modeled protein sequences"),
    (f"{catalog.N_MODES:,}", "predicted binding modes"),
    (f"{catalog.N_FAMILIES:,}", "TF families"),
    (f"{catalog.N_TFS_WITH_JASPAR:,}", "TFs with JASPAR orthologs"),
]


def build_home_example(primary):
    """Preview an exported motif alongside a native render of its selected structure."""
    result_url = f"/search?tf={primary['DBID']}"
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        "An example from the collection",
                        className="home-example-eyebrow",
                    ),
                    html.H4([html.I(primary["TF_Name"]), " · primary binding mode"]),
                    html.P(
                        "See the predicted DNA preference alongside a selected "
                        "protein–DNA structure for this binding mode.",
                        className="home-example-intro",
                    ),
                ]
            ),
            html.Div(
                [
                    html.Figure(
                        [
                            html.Div("Predicted motif", className="home-example-label"),
                            html.Picture(
                                [
                                    html.Source(
                                        srcSet="/assets/home-irf2-logo-narrow.svg",
                                        media=(
                                            "(max-width: 499.98px), "
                                            "(min-width: 768px) and (max-width: 1199.98px)"
                                        ),
                                    ),
                                    html.Img(
                                        id="home-example-logo",
                                        src="/assets/home-irf2-logo.svg",
                                        alt=(
                                            "Predicted irf2 DNA-binding motif. "
                                            "Stack height shows information content in bits."
                                        ),
                                        width=600,
                                        height=220,
                                    ),
                                ],
                            ),
                            html.Figcaption(
                                [
                                    html.Code(primary["motif_id"]),
                                    " · stack height shows information content",
                                ],
                                className="home-example-caption",
                            ),
                        ],
                        className="home-example-figure",
                    ),
                    html.Figure(
                        [
                            html.Div(
                                "Predicted structure", className="home-example-label"
                            ),
                            html.Img(
                                src="/assets/home-irf2-structure.png",
                                alt=(
                                    "AlphaFold 3-predicted irf2 DNA-binding domain "
                                    "in red bound to DNA; the rest of the protein is hidden."
                                ),
                                className="home-example-structure",
                                width=1440,
                                height=882,
                            ),
                            html.Figcaption(
                                "DNA-binding domain (red) and DNA from the selected AlphaFold 3 model",
                                className="home-example-caption",
                            ),
                        ],
                        className="home-example-figure",
                    ),
                ],
                className="home-example-visuals",
            ),
            dcc.Link("Explore irf2 →", href=result_url, className="home-card-cta"),
        ],
        className="container home-example",
    )


def _stat_tile(value, label) -> html.Div:
    """One KPI tile: a large number over a muted caption."""
    return html.Div(
        [
            html.Div(value, className="stat-value"),
            html.Div(label, className="stat-label"),
        ],
        className="stat-tile",
    )


layout = html.Div(
    children=[
        # Hero: periwinkle panel, title, blurb, TF search, stat row, and downloads.
        html.Div(
            className="home-hero",
            children=[
                html.H1("ZebraMotif", className="home-hero-title"),
                html.P(
                    "AlphaFold 3-predicted DNA-binding motifs for zebrafish "
                    "transcription factors.",
                    className="home-hero-subtitle",
                ),
                html.Div(
                    [
                        html.Label(
                            "Search a transcription factor",
                            htmlFor="home-tf-dropdown",
                        ),
                        html.Div(
                            dcc.Dropdown(
                                id="home-tf-dropdown",
                                options=catalog.DROPDOWN_OPTIONS,
                                value=None,
                                placeholder="Gene symbol or Ensembl ID…",
                                searchable=True,
                                clearable=True,
                                optionHeight=44,
                                maxHeight=400,
                            ),
                            className="tf-search-dropdown",
                        ),
                    ],
                    className="home-hero-search",
                ),
                html.Div(
                    [_stat_tile(value, label) for value, label in HOME_STATS],
                    className="stat-grid",
                ),
                html.Div(
                    [
                        dbc.Button(
                            "Download PPMs",
                            href="/downloads",
                            color="light",
                            outline=True,
                        ),
                    ],
                    className="home-hero-cta",
                )
                if DOWNLOADS_ENABLED
                else None,
            ],
        ),
        html.Section(
            [
                html.H2("How to read a result", id="home-result-guide-heading"),
                html.P(
                    "Motifs show predicted DNA preferences; alternate modes show "
                    "other preferences predicted for the same modeled protein. "
                    "Review support counts and structural confidence alongside "
                    "the AlphaFold 3 structure. Some TFs share a modeled "
                    "representative, named in the result. Where available, "
                    "JASPAR ortholog motifs provide a reference comparison. "
                    "Download the probability matrices in MEME format for your analyses."
                ),
                dcc.Link(
                    "Methods and citation →", href="/methods", className="home-card-cta"
                ),
            ],
            className="container home-result-guide",
            **{"aria-labelledby": "home-result-guide-heading"},
        ),
        build_home_example(
            catalog.PRIMARY_MODES.loc[
                catalog.PRIMARY_MODES["DBID"] == HOME_EXAMPLE_DBID
            ].iloc[0]
        ),
    ],
)


def open_home_tf_result(dbid, pathname):
    """Open a selected home-page TF through the canonical Search URL."""
    if (
        pathname != "/"
        or not isinstance(dbid, str)
        or dbid not in catalog.TF2REP_BY_DBID.index
    ):
        raise PreventUpdate
    return f"/search?tf={dbid}"


def register_callbacks(app):
    """Register this page's callbacks on the shared Dash app."""
    app.callback(
        Output("url", "href"),
        Input("home-tf-dropdown", "value"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )(open_home_tf_result)
