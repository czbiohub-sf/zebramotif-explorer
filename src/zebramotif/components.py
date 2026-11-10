"""Sidebar navigation and the footer shared by all pages."""

import dash_bootstrap_components as dbc
from dash import html


def build_sidebar(pages):
    """Build navigation from the manual router's route list."""
    return html.Div(
        [
            html.H4("ZebraMotif", className="sidebar-title"),
            dbc.Nav(
                [
                    dbc.NavLink(page.label, href=route, active="exact")
                    for route, page in pages.items()
                ],
                vertical=True,
                className="sidebar-nav",
            ),
        ],
        id="sidebar",
    )


def build_site_footer(release):
    """Keep release, citation, and contact information available on every page."""
    repositories = release.get("repositories", {})
    source = repositories.get("ZebraMotif", "https://github.com/czbiohub-sf/zebramotif-explorer")
    terms = (
        "https://github.com/google-deepmind/alphafold3/blob/main/OUTPUT_TERMS_OF_USE.md"
    )
    return html.Footer(
        [
            html.Small(f"ZebraMotif · Data release {release['version']}"),
            html.Nav(
                [
                    html.A("Methods & Cite", href="/methods"),
                    html.A("Citation file", href="/documents/CITATION.cff"),
                    html.A(
                        "Data-use terms",
                        href=terms,
                        target="_blank",
                        rel="noopener noreferrer",
                    ),
                    html.A(
                        "Source code",
                        href=source,
                        target="_blank",
                        rel="noopener noreferrer",
                    ),
                    html.A(
                        "Report an issue",
                        href=f"{source}/issues",
                        target="_blank",
                        rel="noopener noreferrer",
                    ),
                ],
                className="d-flex flex-wrap gap-3",
                **{"aria-label": "Resource information"},
            ),
        ],
        className="border-top mt-4 py-3 d-flex flex-wrap justify-content-between gap-3",
    )
