"""Download collections page and its four download button actions."""

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, ctx, dcc, html

from zebramotif import data as catalog


def _download_option(title, button_id, collection, extension):
    """A collection download with its size and a copy-link button."""
    path = f"/downloads/{catalog.DOWNLOADS.version}/{collection}.{extension}"
    return html.Div(
        [
            html.Div(
                [
                    dbc.Button(
                        title,
                        id=button_id,
                        color="primary",
                        outline=True,
                        size="sm",
                        className="download-file-button",
                    ),
                    html.Span("Loading size…", className="download-file-size"),
                ],
                className="download-file-actions",
            ),
            html.Button(
                "Copy link",
                type="button",
                className="btn btn-outline-primary btn-sm download-url-copy",
                **{
                    "aria-label": f"Copy {collection} modes {extension.upper()} link",
                },
            ),
            html.Div(
                className="download-copy-status",
                role="status",
                **{"aria-live": "polite"},
            ),
        ],
        className="download-option",
        **{"data-download-path": path},
    )


def _download_row(
    title, description, n_pwms, batch_btn_id, zip_btn_id, collection
) -> html.Tr:
    """One collection row with MEME and ZIP downloads."""
    return html.Tr(
        [
            html.Td(
                [
                    html.Div(
                        title, className="profile-title", style={"marginBottom": "4px"}
                    ),
                    html.Div(
                        description,
                        style={"fontSize": "0.85rem"},
                    ),
                    html.Div(
                        f"{n_pwms:,} PPMs",
                        style={
                            "color": "var(--text-faint)",
                            "fontSize": "0.8rem",
                            "marginTop": "4px",
                        },
                    ),
                ],
            ),
            html.Td(
                _download_option("MEME file (.meme)", batch_btn_id, collection, "meme")
            ),
            html.Td(
                _download_option(
                    "Motifs + metadata (.zip)", zip_btn_id, collection, "zip"
                )
            ),
        ]
    )


layout = html.Div(
    children=[
        html.Header(
            style={"textAlign": "center", "marginBottom": "30px"},
            children=[html.H1("Download PPMs", style={"color": "var(--heading)"})],
        ),
        dbc.Row(
            dbc.Col(
                html.Div(
                    className="container",
                    children=[
                        html.Table(
                            [
                                html.Thead(
                                    html.Tr(
                                        [
                                            html.Th("Collection"),
                                            html.Th("Batch"),
                                            html.Th("Bundle"),
                                        ]
                                    )
                                ),
                                html.Tbody(
                                    [
                                        _download_row(
                                            "Primary modes",
                                            "One primary PPM per modeled representative.",
                                            catalog.N_PRIMARY,
                                            "btn-primary-batch",
                                            "btn-primary-zip",
                                            "primary",
                                        ),
                                        _download_row(
                                            "All modes",
                                            "Primary and alternate modes for every modeled representative.",
                                            catalog.N_ALL,
                                            "btn-all-batch",
                                            "btn-all-zip",
                                            "all",
                                        ),
                                    ]
                                ),
                            ],
                            className="download-table",
                        ),
                        html.Details(
                            [
                                html.Summary("Format details"),
                                dcc.Markdown(
                                    "Position probability matrices are provided in "
                                    "[minimal MEME motif format](https://meme-suite.org/meme/doc/meme-format.html) "
                                    "(probability matrices, with cluster support as `nsites`).\n\n"
                                    "Each motif's stable `motif_id` is its identifier for tool selection "
                                    "(e.g. `fimo --motif ZM...`); the `MOTIF` line's alternate name lists "
                                    "**every** gene symbol whose TF clusters to that motif, comma-joined. "
                                    "So a TF that shares another's representative PPM (rather than having "
                                    "its own) is still findable: search the file for its symbol, and the "
                                    "`motif_id` on that line is the one carrying its PPM.\n\n"
                                    "ZIP bundles include a README, a TSV mapping each query to its "
                                    "representative and motif IDs with raw mode metrics, release metadata, "
                                    "citation, and terms. The versioned links work directly in scripts.",
                                ),
                            ],
                            className="download-format-details",
                        ),
                        dcc.Markdown(
                            f"Dataset version **{catalog.DOWNLOADS.version}**. "
                            "See [Methods & Cite](/methods), [dataset rights and notices](/documents/LICENSE.md), "
                            "and the [AlphaFold 3 Output Terms of Use]"
                            "(https://github.com/google-deepmind/alphafold3/blob/main/OUTPUT_TERMS_OF_USE.md) "
                            "before reusing the predictions.",
                            className="download-notices",
                        ),
                    ],
                ),
                width=12,
            )
        ),
        # Invisible sinks the download callback writes to (one per button).
        dcc.Download(id="dl-primary-batch"),
        dcc.Download(id="dl-primary-zip"),
        dcc.Download(id="dl-all-batch"),
        dcc.Download(id="dl-all-zip"),
    ],
)


def _meme_zip_writer(collection):
    """Return the shared, documented archive writer for dcc.send_bytes."""

    def write(buffer):
        buffer.write(catalog.DOWNLOADS.archive_bytes(collection))

    return write


def handle_download(*_clicks):
    """Serve the requested PPM collection. One callback fans out to all four download
    sinks; only the one matching the clicked button is populated."""
    no = dash.no_update
    trigger = ctx.triggered_id

    if trigger == "btn-primary-batch":
        return (
            dcc.send_string(
                catalog.DOWNLOADS.meme("primary"),
                "zebramotif_primary_modes.meme",
            ),
            no,
            no,
            no,
        )
    if trigger == "btn-primary-zip":
        return (
            no,
            dcc.send_bytes(
                _meme_zip_writer("primary"), "zebramotif_primary_modes_meme.zip"
            ),
            no,
            no,
        )
    if trigger == "btn-all-batch":
        return (
            no,
            no,
            dcc.send_string(catalog.DOWNLOADS.meme("all"), "zebramotif_all_modes.meme"),
            no,
        )
    if trigger == "btn-all-zip":
        return (
            no,
            no,
            no,
            dcc.send_bytes(_meme_zip_writer("all"), "zebramotif_all_modes_meme.zip"),
        )
    return no, no, no, no


def register_callbacks(app):
    """Register this page's callbacks on the shared Dash app."""
    app.callback(
        Output("dl-primary-batch", "data"),
        Output("dl-primary-zip", "data"),
        Output("dl-all-batch", "data"),
        Output("dl-all-zip", "data"),
        Input("btn-primary-batch", "n_clicks"),
        Input("btn-primary-zip", "n_clicks"),
        Input("btn-all-batch", "n_clicks"),
        Input("btn-all-zip", "n_clicks"),
        prevent_initial_call=True,
    )(handle_download)
