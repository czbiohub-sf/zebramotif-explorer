"""Create the ZebraMotif dashboard and orchestrate its manual page router."""

import os
from types import ModuleType
from typing import NamedTuple

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate

from zebramotif import data as catalog
from zebramotif.components import build_sidebar, build_site_footer
from zebramotif.downloads import DOWNLOADS_ENABLED
from zebramotif.pages import downloads, home, methods, not_found, search
from zebramotif.routes import register_routes

# App setup

# suppress_callback_exceptions: page content is rendered dynamically by the router
# callback, so components referenced by callbacks aren't all present at initial load.
# Hanken Grotesk (body) + STIX Two Text (serif display) are the Zebrahub typefaces;
# loading them here lets assets/styles.css reference them (see the theme tokens there).
GOOGLE_FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=Hanken+Grotesk:wght@400;500;600;700&"
    "family=STIX+Two+Text:wght@500;600;700&display=swap"
)

app = dash.Dash(
    __name__,
    title="ZebraMotif",
    update_title="Loading · ZebraMotif",
    meta_tags=[
        {
            "name": "description",
            "content": (
                "Explore predicted DNA-binding motifs and protein–DNA structures "
                "for zebrafish transcription factors."
            ),
        }
    ],
    external_stylesheets=[dbc.themes.BOOTSTRAP, GOOGLE_FONTS],
    compress=True,
    suppress_callback_exceptions=True,
)
app.index_string = app.index_string.replace("<html>", '<html lang="en">').replace(
    "{%favicon%}",
    '{%favicon%}\n        <link rel="icon" type="image/svg+xml"'
    f' href="{app.get_asset_url("favicon.svg")}">',
)
server = app.server


class Page(NamedTuple):
    label: str
    module: ModuleType


# Add a page here to include its navigation link, layout, and optional callbacks.
PAGES = {
    "/": Page("Home", home),
    "/search": Page("Search", search),
    **({"/downloads": Page("Downloads", downloads)} if DOWNLOADS_ENABLED else {}),
    "/methods": Page("Methods & Cite", methods),
}

sidebar = build_sidebar(PAGES)
content = html.Div(
    id="content",
    children=[html.Div(id="page-content"), build_site_footer(catalog.RELEASE_METADATA)],
)

app.layout = html.Div(
    [
        # Notify the Search page's location when a callback changes the query.
        dcc.Location(id="url", refresh="callback-nav"),
        dcc.Store(id="rendered-route", data=None),
        sidebar,
        content,
    ]
)


@app.callback(
    Output("page-content", "children"),
    Output("rendered-route", "data"),
    Input("url", "pathname"),
    State("rendered-route", "data"),
)
def render_page(pathname, rendered_route):
    """Render the requested page or a helpful missing-page view."""
    # Replacing an already displayed page resets its controls and closes the menu.
    if not pathname or pathname == rendered_route:
        raise PreventUpdate
    page = PAGES.get(pathname)
    return page.module.layout if page else not_found.layout(pathname), pathname


for page in PAGES.values():
    register_callbacks = getattr(page.module, "register_callbacks", None)
    if register_callbacks is not None:
        register_callbacks(app)
register_routes(app, PAGES)


# Finish Dash's lazy setup before Gunicorn threads can request component scripts.
server.test_client().get("/")


def main() -> None:
    """Start the dashboard using the configured host and port."""
    app.run(
        host=os.environ.get("ZEBRAMOTIF_HOST", "127.0.0.1"),
        port=int(os.environ.get("ZEBRAMOTIF_PORT", "8099")),
        debug=False,
    )


if __name__ == "__main__":
    main()
