"""Molstar structure parsing, representations, camera focus, and color legends."""

import gzip
import os
from functools import lru_cache

import pandas as pd
from dash import html
from dash_molstar.utils import molstar_helper
from dash_molstar.utils.representations import Representation

from zebramotif import data as catalog

# Molstar viewer chrome: hide the side panels/sequence/log so the embedded viewer is just
# the 3D canvas. `layout` is fixed at init (it cannot change via callback). dash-molstar
# passes `canvas3d` to the plugin spec. Disable depth fog and distance clipping in every
# view; structure_viewer.js also prevents camera snapshots from restoring these effects.
VIEWER_LAYOUT = {
    "layoutShowControls": False,
    "layoutShowSequence": False,
    "layoutShowLog": False,
    "layoutShowLeftPanel": False,
    "viewportShowExpand": False,
    "canvas3d": {
        "cameraFog": {"name": "off", "params": {}},
        "cameraClipping": {"far": False},
    },
}

# Match Mol*'s native plddt-confidence theme, including its inclusive upper bounds.
PLDDT_COLORS = [
    ("Very high (>90)", 0x0053D6),
    ("Confident (>70 to 90)", 0x65CBF3),
    ("Low (>50 to 70)", 0xFFDB13),
    ("Very low (≤50)", 0xFF7D45),
]
NON_CONTACT_COLOR = 0xB0B0B0

# Colors (0xRRGGBB) for the "Show DNA contacts" view: each DNA-contacting chain-A residue is
# colored by what it reaches on the DNA. Contact modes are mutually exclusive per residue, so
# CONTACT_ORDER just fixes a stable legend/component order (most informative first).
CONTACT_COLORS = {
    "base": 0xE85D04,  # orange: base-edge contact (sequence-specific readout)
    "mixed": 0x9D4EDD,  # purple: contacts both a base edge and the backbone
    "backbone": 0x0E9DE4,  # cyan: phosphate-backbone contact (non-specific)
}
CONTACT_LABELS = {
    "base": "Base contact (sequence-specific)",
    "mixed": "Base + backbone contact",
    "backbone": "Backbone contact",
}
CONTACT_ORDER = ["base", "mixed", "backbone"]

# The AF3 models put the protein on author chain "A" (DNA on B/C); the DBD residue numbers
# from dbd_domains.parquet are author residue numbers along that chain.
PROTEIN_CHAIN = "A"


@lru_cache(maxsize=64)
def _read_cif(structure_path):
    """Decompressed CIF text for an installed structure, cached across selections/toggles."""
    with gzip.open(f"{catalog.DATA_DIR}/{structure_path}", "rt") as fh:
        return fh.read()


@lru_cache(maxsize=64)
def _chain_residues(structure_path):
    """Map each author chain id -> sorted list of its author residue numbers.

    Parsed from the `_atom_site` loop to restrict the protein to annotated domains
    and keep contact representations separate from the remaining cartoon.
    """
    cif = _read_cif(structure_path)
    chains = {}
    in_atoms = False
    for line in cif.splitlines():
        if line.startswith(("ATOM", "HETATM")):
            in_atoms = True
            cols = line.split()
            # auth_seq_id, auth_asym_id are the last two columns before pdbx_PDB_model_num.
            auth_seq, auth_asym = cols[-3], cols[-2]
            chains.setdefault(auth_asym, set()).add(int(auth_seq))
        elif in_atoms:
            break  # atom records are contiguous; stop once the loop ends
    return {chain: sorted(res) for chain, res in chains.items()}


def _cartoon(color):
    """A uniform-color cartoon representation."""
    rep = Representation(type="cartoon", color="uniform")
    rep.set_color_params({"value": color})
    return rep


def _contact_reps(color):
    """Representations for a DNA-contact residue group: the uniform-color cartoon plus a
    ball-and-stick, so individual contacting side chains stand out from the protein cartoon
    (contacts are scattered single residues, easy to miss as cartoon segments alone)."""
    sticks = Representation(type="ball-and-stick", color="uniform")
    sticks.set_color_params({"value": color})
    return [_cartoon(color), sticks]


def structure_data(structure_path, dbd=None, contacts=None):
    """Parse a primary mode's gzipped AF3 `.cif` into molstar `data`, or None if unavailable.

    `structure_path` is the `pwm_modes` value (relative to the installed dataset); it is set
    on primary rows only and null when the source `.cif` was missing (see SCHEMA.md).

    The protein uses pLDDT colors unless the contacts view is active. Explicit components
    suppress the standard representation (`preset` kind `empty`) so hidden residues cannot reappear behind the
    domain view. DNA chains (B/C) retain their `polymer-id` coloring and base visuals.

    - `dbd`: a list of `(start, end, label)` tuples: show only these DNA-binding domains
      on chain A, alongside the DNA. Domains with the same label share a component.
    - `contacts`: a `{residue_num: mode}` map: those chain-A residues are drawn (cartoon +
      ball-and-stick) in the per-mode CONTACT_COLORS (base / mixed / backbone), while
      non-contact protein residues are grey. An empty map keeps this view active;
      None uses pLDDT coloring.

    Visible protein uses Mol*'s pLDDT confidence theme, which reads CIF B-factor values
    when Model Archive quality scores are absent. The contacts view replaces confidence
    coloring without drawing residues twice. The domain-only view hides outside contacts.
    """
    if structure_path is None or (
        isinstance(structure_path, float) and pd.isna(structure_path)
    ):
        return None
    if not os.path.exists(f"{catalog.DATA_DIR}/{structure_path}"):
        return None
    cif = _read_cif(structure_path)

    chain_residues = _chain_residues(structure_path)
    protein = chain_residues.get(PROTEIN_CHAIN, [])
    if dbd:
        protein = [
            r for r in protein if any(start <= r <= end for start, end, _ in dbd)
        ]

    # The bundled Mol* supports this theme; the Python Representation allowlist
    # predates it. create_component also accepts representation dicts.
    protein_rep = (
        _cartoon(NON_CONTACT_COLOR)
        if contacts is not None
        else {"type": "cartoon", "color": "plddt-confidence"}
    )

    components = []

    # DNA-contact residues, one component per contact mode. These take precedence: any residue
    # colored here is excluded from the other protein components below.
    contacts = contacts or {}
    contact_res = set(contacts)
    by_mode = {}
    for res in protein:
        mode = contacts.get(res)
        if mode:
            by_mode.setdefault(mode, []).append(res)
    for mode in CONTACT_ORDER:
        res = by_mode.get(mode)
        if res:
            components.append(
                molstar_helper.create_component(
                    f"DNA contact: {CONTACT_LABELS.get(mode, mode)}",
                    molstar_helper.get_targets(PROTEIN_CHAIN, residue=res, auth=True),
                    representation=_contact_reps(CONTACT_COLORS[mode]),
                )
            )

    # Keep domain labels with pLDDT colors, or grey in the contacts view. The protein has been
    # restricted to these domains; contacts retain their colors within that selection.
    dbd_res = []
    if dbd:
        res_label = {}
        for r in protein:
            if r in contact_res:
                continue
            for start, end, label in dbd:
                if start <= r <= end:
                    res_label[r] = label
                    break
        by_label = {}
        for r in protein:
            if r in res_label:
                by_label.setdefault(res_label[r], []).append(r)
        for label, res in by_label.items():
            components.append(
                molstar_helper.create_component(
                    f"DNA-binding domain: {label}",
                    molstar_helper.get_targets(PROTEIN_CHAIN, residue=res, auth=True),
                    representation=protein_rep,
                )
            )
        dbd_res = list(res_label)

    # With domain filtering off, show the rest of the protein in pLDDT colors or grey.
    colored = contact_res | set(dbd_res)
    protein_rest = [r for r in protein if r not in colored]
    if protein_rest:
        components.append(
            molstar_helper.create_component(
                "Protein",
                molstar_helper.get_targets(
                    PROTEIN_CHAIN, residue=protein_rest, auth=True
                ),
                representation=protein_rep,
            )
        )

    # Every other chain (the DNA) untouched: drawn with the default per-chain coloring so it
    # looks the same as in the unhighlighted view, rather than being recolored. The nucleotide
    # `visuals` are set explicitly. A bare cartoon component only draws the backbone trace, so
    # without these the base rings/blocks (the "rungs") disappear from the double helix.
    dna_targets = [
        molstar_helper.get_targets(chain, auth=True)
        for chain in chain_residues
        if chain != PROTEIN_CHAIN
    ]
    if dna_targets:
        dna_rep = Representation(type="cartoon", color="polymer-id")
        dna_rep.set_type_params(
            {
                "visuals": [
                    "polymer-trace",
                    "polymer-gap",
                    "nucleotide-ring",
                    "nucleotide-atomic-ring-fill",
                    "nucleotide-atomic-bond",
                    "nucleotide-atomic-element",
                ]
            }
        )
        components.append(
            molstar_helper.create_component("DNA", dna_targets, representation=dna_rep)
        )

    return molstar_helper.parse_molecule(
        cif, fmt="cif", component=components, preset={"kind": "empty"}
    )


def structure_focus(structure_path, dbd):
    """Frame the annotated binding domains and DNA, leaving disordered tails out."""
    chains = _chain_residues(structure_path)
    domain_residues = [
        r
        for r in chains.get(PROTEIN_CHAIN, [])
        if any(start <= r <= end for start, end, _ in (dbd or []))
    ]
    targets = []
    if domain_residues:
        targets.append(
            molstar_helper.get_targets(
                PROTEIN_CHAIN, residue=domain_residues, auth=True
            )
        )
    targets.extend(
        molstar_helper.get_targets(chain, auth=True)
        for chain in chains
        if chain != PROTEIN_CHAIN
    )
    return molstar_helper.get_focus(targets) if targets else None


def build_contacts_legend(contacts):
    """Explain the visible contact modes and the grey non-contact protein."""
    present = set(contacts.values())
    entries = [
        (CONTACT_LABELS[mode], CONTACT_COLORS[mode])
        for mode in CONTACT_ORDER
        if mode in present
    ]
    entries.append(("Non-contact residue", NON_CONTACT_COLOR))
    items = []
    for label, color in entries:
        items.append(
            html.Div(
                [
                    html.Span(
                        style={
                            "display": "inline-block",
                            "width": "12px",
                            "height": "12px",
                            "borderRadius": "2px",
                            "backgroundColor": f"#{color:06X}",
                            "marginRight": "6px",
                        }
                    ),
                    html.Span(label),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "marginRight": "16px",
                },
            )
        )
    items.append(
        html.P(
            "Contact highlights are pooled across predicted structures and may differ "
            "from contacts in the displayed model.",
            className="confidence-scope mb-0",
            style={"flexBasis": "100%"},
        )
    )
    return items


def build_plddt_legend():
    """Explain the native confidence colors."""
    items = [html.Strong("pLDDT", className="me-2")]
    for label, color in PLDDT_COLORS:
        items.append(
            html.Span(
                [
                    html.Span(
                        className="structure-color-swatch",
                        style={"backgroundColor": f"#{color:06X}"},
                        **{"aria-hidden": "true"},
                    ),
                    label,
                ],
                className="structure-color-key",
            )
        )
    return items
