"""Missing-page content for the manual router."""

from dash import html


def layout(pathname):
    """Give an unknown page a useful destination without hiding the bad URL."""
    return html.Div(
        [
            html.H1("Page not found"),
            html.P(["There is no ZebraMotif page at ", html.Code(pathname), "."]),
            html.P(
                [
                    html.A(
                        "Search motifs",
                        href="/search",
                        className="btn btn-primary me-2",
                    ),
                    html.A("Go to Home", href="/", className="btn btn-outline-primary"),
                ]
            ),
        ],
        className="container",
    )
