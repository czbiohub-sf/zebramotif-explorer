import re
from decimal import ROUND_HALF_UP, Decimal

import numpy as np

# Column order of every PPM in the installed dataset (see SCHEMA.md).
BASES = ["A", "C", "G", "T"]


def base_gene_dbid(dbid: str) -> str:
    """Return the parent gene ID for an entry with a terminal numeric domain suffix."""
    return re.sub(r"_[0-9]+$", "", dbid)


def display_tf_name(name: str) -> str:
    """Show domain-specific TF names as, for example, 'dacha (domain 1)'."""
    return re.sub(r"_domain(\d+)$", r" (domain \1)", name)


def format_number(value, *, percent=False, decimal_places=None, missing="—") -> str:
    """Round for display; default to one decimal for percentages, up to three otherwise."""
    if value is None:
        return missing
    number = Decimal(str(value))
    if not number.is_finite():
        return missing
    if percent:
        number *= 100
    precision = decimal_places if decimal_places is not None else (1 if percent else 3)
    rounded = number.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
    if not rounded:
        rounded = abs(rounded)
    text = format(rounded, "f")
    if precision == 3:
        text = text.rstrip("0").rstrip(".")
    return f"{text}%" if percent else text


def as_pwm(cell) -> np.ndarray:
    """Coerce a stored `pwm` cell into a dense (L, 4) float array.

    The pyarrow engine reads the list-valued `pwm` column back as an object array whose
    elements are themselves length-4 arrays, so it needs stacking rather than a plain
    ``np.asarray(..., dtype=float)``.

    Args:
        cell: A single `pwm` value from pwm_modes.parquet.

    Returns:
        (L, 4) float array of base probabilities (columns A, C, G, T).
    """

    return np.vstack([np.asarray(row, dtype=float) for row in cell])


# MEME minimal-format file header (version 4), uniform ACGT background. Shared by the
# batch file and every individual motif file (see http://meme-suite.org/doc/meme-format.html).
MEME_HEADER = (
    "MEME version 4\n\n"
    "ALPHABET= ACGT\n\n"
    "strands: + -\n\n"
    "Background letter frequencies\n"
    "A 0.25 C 0.25 G 0.25 T 0.25\n"
)


def meme_record(row, name=None) -> str:
    """Format one binding-mode row as a MEME `MOTIF` block (no file header).

    The stored `pwm` is already a probability matrix, which is exactly what MEME's
    letter-probability matrix wants; `nsites` is the mode's cluster support (`n_members`).

    MEME tools select a motif by its primary identifier (the `motif_id`), not by gene
    symbol. `name` becomes the optional alternate name: a single token (no spaces or `=`)
    used so callers can pack the full set of clustered gene symbols (comma-joined) onto the
    line, making each member TF greppable back to its `motif_id`.

    Args:
        row: A single row of pwm_modes (a pandas Series).
        name: Alternate-name token; defaults to the row's own `TF_Name`.

    Returns:
        The `MOTIF` block as text, without a trailing newline.
    """

    pwm = as_pwm(row["pwm"])
    alt_name = row["TF_Name"] if name is None else name
    lines = [
        f"MOTIF {row['motif_id']} {alt_name}",
        "",
        (
            "letter-probability matrix: "
            f"alength= 4 w= {pwm.shape[0]} nsites= {int(row['n_members'])} E= 0"
        ),
    ]
    lines += ["  ".join(f"{p:.6f}" for p in position) for position in pwm]
    return "\n".join(lines)


def meme_document(rows, names=None) -> str:
    """Full MEME file text: the shared header followed by one `MOTIF` block per row.

    Args:
        rows: A DataFrame of pwm_modes rows, in the desired file order.
        names: Optional mapping of `motif_id` -> alternate-name token; rows missing from
            it fall back to their own `TF_Name`.

    Returns:
        Complete MEME-format document text.
    """

    blocks = [
        meme_record(row, None if names is None else names.get(row["motif_id"]))
        for _, row in rows.iterrows()
    ]
    return MEME_HEADER + "\n" + "\n\n".join(blocks) + "\n"


def nucleotide_color_dict() -> dict:
    """Returns dictionary mapping nucleotide to color.

    Colors follow the common WebLogo / MEME convention (A green, C blue,
    G orange/gold, T red).

    Returns:
        dict: Key is nucleotide, value is hex color.
    """

    color_dict = {
        "A": "#2ca02c",
        "C": "#1f77b4",
        "G": "#ff7f0e",
        "T": "#d62728",
    }

    return color_dict
