"""Methods, interpretation, and citation content for the public website."""

from collections.abc import Mapping

import dash_bootstrap_components as dbc
from dash import dcc, html

from zebramotif import data as catalog

AF3_OUTPUT_TERMS_URL = (
    "https://github.com/google-deepmind/alphafold3/blob/main/OUTPUT_TERMS_OF_USE.md"
)
AF3_CONFIDENCE_URL = (
    "https://github.com/google-deepmind/alphafold3/blob/main/docs/output.md"
    "#confidence-metrics"
)


def _section(title, children, anchor):
    return html.Section(
        [html.H2(title, className="h4"), *children],
        id=anchor,
        className="container methods-section",
        **{"aria-label": title},
    )


def _table(headings, rows):
    """Let narrow screens scroll only a table instead of the whole page."""
    return dbc.Table(
        [
            html.Thead(html.Tr([html.Th(label, scope="col") for label in headings])),
            html.Tbody(
                [
                    html.Tr(
                        [html.Th(row[0], scope="row")]
                        + [html.Td(value) for value in row[1:]]
                    )
                    for row in rows
                ]
            ),
        ],
        responsive=True,
        size="sm",
        class_name="mb-3",
    )


def _contents():
    return html.Nav(
        [
            html.Span("On this page", className="methods-toc-label"),
            *[
                html.A(label, href=f"#{anchor}")
                for label, anchor in [
                    ("Workflow", "methods-predictions"),
                    ("Sequence logos", "methods-logos"),
                    ("Scores", "methods-scores"),
                    ("Data & versions", "methods-dataset"),
                    ("Citation", "methods-cite"),
                    ("Use & attribution", "methods-terms"),
                ]
            ],
        ],
        className="methods-toc",
        **{"aria-label": "On this page"},
    )


def _workflow(methods):
    """Responsive adaptation of Fig4 panel A, ending at predicted binding modes."""
    steps = [
        (
            "AlphaFold 3",
            "Select confident structures",
            f"Keep up to {methods['num_specs']} TF–DNA models, ranked by structural confidence.",
            "structures",
        ),
        (
            "NA-MPNN",
            "Predict base preferences",
            "Make one position probability matrix (PPM) from each selected structure.",
            "preferences",
        ),
        (
            "UPGMA",
            "Group similar predictions",
            f"Cluster the matrices at a correlation cutoff of {methods['cor_threshold']}.",
            "clusters",
        ),
        (
            "Consensus",
            "Reveal binding modes",
            "The largest cluster gives the primary motif; up to "
            f"{methods['maximum_alternates']} others give alternates.",
            "modes",
        ),
    ]
    return html.Figure(
        [
            html.Ol(
                [
                    html.Li(
                        [
                            html.Img(
                                src=f"/assets/methods-{asset}.svg",
                                alt=(
                                    "Predicted TF–DNA structures, with ipTM increasing "
                                    "to the right and DNA-binding domain pLDDT "
                                    "increasing upward."
                                    if asset == "structures"
                                    else ""
                                ),
                                width=240,
                                height=136,
                                className="methods-workflow-graphic",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Span(
                                                str(index),
                                                className="methods-workflow-number",
                                            ),
                                            html.Span(tool),
                                        ],
                                        className="methods-workflow-label",
                                    ),
                                    html.H3(title),
                                    html.P(description),
                                ]
                            ),
                        ],
                        className="methods-workflow-step",
                    )
                    for index, (tool, title, description, asset) in enumerate(steps, 1)
                ],
                className="methods-workflow",
                role="list",
            ),
            html.Figcaption(
                "Multiple structures can support the same DNA preference. Clustering "
                "turns these predictions into distinct binding modes. Illustrations are schematic.",
                className="methods-workflow-caption",
            ),
        ],
        className="methods-workflow-figure",
        **{
            "aria-label": "From predicted TF–DNA structures to consensus binding motifs"
        },
    )


def build_methods_page(counts: Mapping[str, int] | None = None) -> html.Div:
    """Build Methods & Cite from the loaded metadata and optional count overrides."""
    metadata = catalog.RELEASE_METADATA
    totals = {**metadata["counts"], **(counts or {})}
    snapshots = metadata.get("documented_snapshots", {})
    source_dates = [
        (label, snapshots[key])
        for label, key in [
            ("Motifs", "motifs"),
            ("Confidence summaries", "confidence_metrics"),
            ("Domain annotations", "domain_annotation_refresh"),
            ("Catalog and sequence metadata", "catalog_and_sequence_metadata_refresh"),
        ]
        if snapshots.get(key)
    ]
    methods = metadata["methods"]
    versions = metadata["reported_versions"]
    annotation_versions = metadata["observed_annotation_versions"]
    website = metadata["repositories"]["ZebraMotif"]
    pipeline = metadata["repositories"]["af3-tf-motif"]
    citation = metadata["citation"]
    creators = "; ".join(
        f"{creator['family_name']}, {creator['given_name']}"
        for creator in metadata["creators"]
    )
    dataset_citation = (
        f"{creators}. {metadata['title']}. Version {metadata['version']}."
    )
    doi = metadata.get("doi")
    doi_content = (
        html.A(f"doi:{doi}", href=f"https://doi.org/{doi}")
        if doi
        else "No dataset DOI is recorded for this version. "
        "Use the version-specific deposit citation when available."
    )

    return html.Div(
        [
            html.Header(
                [
                    html.H1("Methods & Cite"),
                    html.P(
                        "How the predictions were made, how to interpret them, "
                        "and how to cite this dataset.",
                        className="text-muted",
                    ),
                ],
                style={"textAlign": "center", "marginBottom": "24px"},
            ),
            _contents(),
            _section(
                "From structure to binding modes",
                [
                    html.P(
                        "For each modeled zebrafish transcription factor, structure-based "
                        "nucleotide preferences are distilled into a primary motif and "
                        "alternate binding modes.",
                        className="methods-intro",
                    ),
                    _workflow(methods),
                    html.Details(
                        [
                            html.Summary("Selection, clustering, and representatives"),
                            html.Dl(
                                [
                                    html.Dt("Catalog and representatives"),
                                    html.Dd(
                                        "AnimalTFDB 4.0 supplies the TF catalog and family labels. "
                                        "Related protein sequences are grouped and a representative "
                                        "is modeled with candidate DNA sequences. Searches show a TF's "
                                        "own prediction when available, or its recorded representative's. "
                                        "Separately modeled domains have their own search entries."
                                    ),
                                    html.Dt("Model selection"),
                                    html.Dd(
                                        f"Up to {methods['num_specs']} predictions are selected by the "
                                        "product of their ipTM and DNA-binding-domain pLDDT percentile "
                                        "ranks. NA-MPNN predicts a matrix of A, C, G, T probabilities "
                                        "at each DNA position for each selected structure."
                                    ),
                                    html.Dt("Clustering and consensus"),
                                    html.Dd(
                                        "UPGMA uses average-linkage clustering with a correlation merge "
                                        f"cutoff of {methods['cor_threshold']}. Member matrices are aligned "
                                        "and their probabilities averaged into a consensus motif. "
                                        "The largest cluster supplies the primary mode; equal-size ties "
                                        "are broken by member confidence ranks."
                                    ),
                                    html.Dt("Displayed structure and domains"),
                                    html.Dd(
                                        "The displayed AlphaFold 3 structure is the highest-ranked "
                                        "member of the primary binding mode. "
                                        "Domain annotations describe the modeled protein; "
                                        "residue coordinates are inclusive and 1-based."
                                    ),
                                ]
                            ),
                        ],
                        className="methods-details",
                    ),
                    html.P(
                        html.A("Prediction pipeline and methods", href=pipeline),
                        className="methods-source-link",
                    ),
                ],
                "methods-predictions",
            ),
            _section(
                "Read the sequence logos",
                [
                    html.P(
                        "By default, letter stacks show information content (IC) in bits. "
                        "The Logo scale selector and reverse-complement switch update "
                        "the primary and all aligned alternate motifs together."
                    ),
                    html.P(
                        "Hover over a position to see its base probabilities and "
                        "stack height. Changing the scale or orientation affects "
                        "only the display; downloads contain the original "
                        "probability matrices."
                    ),
                    html.Details(
                        [
                            html.Summary("IC and log-odds formulas"),
                            html.P(
                                "Both views use the same base probabilities and a "
                                "uniform background of 0.25 for each base."
                            ),
                            html.Dl(
                                [
                                    html.Dt("Information content (IC, default)"),
                                    html.Dd(
                                        "The stack height is IC = 2 + Σ p log₂(p) bits, "
                                        "summing over A, C, G, and T with 0 log₂(0) = 0. "
                                        "Each letter's height is p × IC. This is the "
                                        "conventional information-content view used for "
                                        "JASPAR sequence logos."
                                    ),
                                    html.Dt("Log-odds"),
                                    html.Dd(
                                        "Each letter's height is max(0, log₂(p/0.25)), "
                                        "where p is that base's probability. Bases at or "
                                        "below background are hidden. The y-axis shows "
                                        "enrichment; the stack's total height is not "
                                        "information content."
                                    ),
                                ]
                            ),
                            html.P(
                                "For example, a 50/50 A/G column has a 2-bit stack in "
                                "log-odds view (1 bit per letter), but a 1-bit stack in "
                                "IC view (0.5 bits per letter). A fully conserved base "
                                "reaches 2 bits in either view; a uniform column has "
                                "zero height in both.",
                                className="mb-0",
                            ),
                        ],
                        className="methods-details",
                    ),
                ],
                "methods-logos",
            ),
            _section(
                "Read the scores",
                [
                    html.P(
                        "Prediction support, structural confidence, and ortholog "
                        "comparisons describe separate evidence. Qualitative "
                        "bands are not calibrated probabilities of biological "
                        "correctness."
                    ),
                    html.Dl(
                        [
                            html.Dt("Support"),
                            html.Dd(
                                "The number of selected specificity predictions "
                                "in a mode divided by the selection target "
                                f"({methods['num_specs']}). It describes agreement "
                                "among predictions, not binding affinity."
                            ),
                            html.Dt("AF3 confidence"),
                            html.Dd(
                                "Domain pLDDT (0–100) estimates local structural "
                                "confidence; protein–DNA ipTM (0–1) estimates "
                                "confidence in the relative placement of the "
                                "chains. The page shows medians and 10th–90th "
                                "percentile ranges for top-ranked predictions "
                                "pooled across modes, not separate confidence "
                                "estimates for each binding mode."
                            ),
                            html.Dt("DBD similarity"),
                            html.Dd(
                                "Sequence similarity in the DNA-binding domain (DBD) "
                                "to the ortholog associated with a JASPAR reference "
                                "motif, expressed as a percentage."
                            ),
                            html.Dt("Motif similarity"),
                            html.Dd(
                                "HOMER similarity between a predicted consensus "
                                "motif and its JASPAR reference. Higher values "
                                "indicate closer motif agreement. "
                                "The empirical p-value is the fraction of JASPAR motifs "
                                "matching the prediction at least as well as its assigned reference."
                            ),
                            html.Dt("IC recovery"),
                            html.Dd(
                                "Reference information-content-weighted motif "
                                "recovery (0–100%). It scores aligned base "
                                "preferences above a uniform background; "
                                "uncovered reference positions contribute zero."
                            ),
                        ],
                        className="methods-score-definitions mb-3",
                    ),
                    html.P(
                        "An ortholog comparison does not establish experimental "
                        "binding in zebrafish. Missing reference motifs, domain "
                        "annotations, or confidence summaries are displayed "
                        "explicitly. A zero domain-pLDDT estimate means the "
                        "domain estimate is unavailable."
                    ),
                    html.Details(
                        [
                            html.Summary("Display thresholds"),
                            _table(
                                ("Metric", "Low", "Medium", "High"),
                                [
                                    ("Support", "<10%", "10–<30%", "≥30%"),
                                    ("Motif similarity", "<0.6", "0.6–<0.8", "≥0.8"),
                                    ("IC recovery", "<40%", "40–<70%", "≥70%"),
                                ],
                            ),
                            html.P(
                                "Domain pLDDT: very low <50, low 50–<70, high "
                                "70–<90, very high ≥90. Protein–DNA ipTM: low "
                                "<0.6, uncertain 0.6–0.8, high >0.8. AF3 labels "
                                "describe the median."
                            ),
                        ],
                        className="confidence-help",
                    ),
                    html.P(
                        html.A(
                            "AlphaFold 3 confidence definitions",
                            href=AF3_CONFIDENCE_URL,
                        ),
                        className="mb-0 mt-3",
                    ),
                ],
                "methods-scores",
            ),
            _section(
                "Dataset and source versions",
                [
                    html.P(
                        f"Dataset version {metadata['version']} contains "
                        f"{totals['catalog_genes']:,} catalog genes, "
                        f"{totals['primary_modes']:,} primary modes, and "
                        f"{totals['alternate_modes']:,} alternates. "
                        f"There are {totals['query_entries']:,} search entries, "
                        f"including {totals['domain_entries']} domain entries. "
                    ),
                    html.P(metadata["release_label"])
                    if metadata.get("release_label")
                    else None,
                    _table(("Dataset component", "Snapshot / refresh"), source_dates)
                    if source_dates
                    else None,
                    _table(
                        ("Resource", "Reported version"),
                        [
                            (resource, value)
                            for resource, value in versions.items()
                            if resource != "basis"
                        ]
                        + [
                            (
                                "PROSITE",
                                annotation_versions["PROSITE Profiles"],
                            )
                        ],
                    ),
                    html.P(
                        "Versions describe the documented pipeline. "
                        + metadata["reference_sequence_provenance"]["note"]
                    ),
                    html.P(
                        [
                            html.A(
                                "Dataset schema",
                                href="/documents/SCHEMA.md",
                            ),
                            " · ",
                            html.A(
                                "Provenance",
                                href="/documents/PROVENANCE.json",
                            ),
                            " · ",
                            dcc.Link("Download motifs", href="/downloads"),
                        ],
                        className="mb-0",
                    ),
                ],
                "methods-dataset",
            ),
            _section(
                "Cite and contact",
                [
                    html.P(dataset_citation),
                    html.P(doi_content, className="text-muted"),
                    html.P(
                        "When reporting a result, include the queried gene or "
                        "Ensembl ID, modeled representative, motif ID, and "
                        "dataset version."
                    ),
                    html.P(
                        [
                            "Please also cite AlphaFold 3: ",
                            citation["alphafold3"]["text"],
                            " ",
                            html.A("Paper and DOI", href=citation["alphafold3"]["url"]),
                            (
                                ". Cite the source resources relevant to your "
                                "analysis, including AnimalTFDB and JASPAR."
                            ),
                        ]
                    ),
                    html.P(
                        [
                            html.A(
                                "Dataset citation metadata",
                                href="/documents/CITATION.cff",
                            ),
                            " · ",
                            html.A("Website code", href=website),
                            " · ",
                            html.A("Prediction pipeline", href=pipeline),
                            " · ",
                            html.A(
                                "Questions and issue reports",
                                href=metadata["contact_url"],
                            ),
                        ],
                        className="mb-0",
                    ),
                ],
                "methods-cite",
            ),
            _section(
                "Use and attribution",
                [
                    html.P(
                        "AlphaFold 3 structures and derivatives, including "
                        "predicted motifs, confidence summaries, and DNA-contact "
                        "annotations, are provided under the AlphaFold 3 Output "
                        "Terms of Use for non-commercial research. They are "
                        "not intended for clinical use. Reference annotations "
                        "retain their providers' terms; the repositories' MIT "
                        "licenses apply to software."
                    ),
                    html.P(
                        [
                            html.A(
                                "AlphaFold 3 Output Terms of Use",
                                href=metadata["terms"]["alphafold3_output_terms_url"],
                            ),
                            " · ",
                            html.A(
                                "Dataset license and attribution",
                                href="/documents/LICENSE.md",
                            ),
                        ],
                        className="mb-0",
                    ),
                ],
                "methods-terms",
            ),
        ],
        className="methods-page",
    )


layout = build_methods_page(catalog.METHODS_COUNTS)
