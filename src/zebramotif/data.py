"""Release tables and lookup indexes, loaded once per worker and read by callbacks.

Keep user selections in Dash stores; callbacks must not mutate these shared tables.
"""

import json
from pathlib import Path

import pandas as pd

from zebramotif.dataset import require_data_directory
from zebramotif.downloads import MotifDownloads
from zebramotif.utils import display_tf_name


def load_release_metadata(data_dir: Path | None = None) -> dict:
    """Read the versioned metadata shared by the Methods page and downloads."""
    data_dir = data_dir or require_data_directory()
    return json.loads((data_dir / "release_metadata.json").read_text(encoding="utf-8"))


# Data loading

DATA_DIR = require_data_directory()
RELEASE_METADATA = load_release_metadata(DATA_DIR)

MODES = pd.read_parquet(f"{DATA_DIR}/pwm_modes.parquet", engine="pyarrow")
TF2REP = pd.read_parquet(f"{DATA_DIR}/tf_to_rep.parquet", engine="pyarrow")

# DBID -> binding-mode rows (primary first, then alternates by rank).
MODES_SORTED = MODES.sort_values(
    ["DBID", "tier", "mode_rank"],
    key=lambda c: c.map({"primary": 0, "alternate": 1}) if c.name == "tier" else c,
)
MODES_BY_DBID = {dbid: sub for dbid, sub in MODES_SORTED.groupby("DBID")}

# Download collections (grouped per TF: primary first, then its alternates). The
# "non-redundant" set is primary modes only; "redundant" adds the alternate modes.
PRIMARY_MODES = MODES_SORTED[MODES_SORTED["tier"] == "primary"]
PRIMARY_BY_MOTIF_ID = PRIMARY_MODES.set_index("motif_id", drop=False)
ALL_MODES = MODES_SORTED
MODES_BY_MOTIF_ID = ALL_MODES.set_index("motif_id", drop=False)
if not MODES_BY_MOTIF_ID.index.is_unique:
    raise ValueError("Each exported motif must have a unique motif ID.")

# Alternate-name token for each motif in the MEME downloads: every gene symbol that
# clusters to the motif's representative (comma-joined, sorted, deduped). MEME selects a
# motif by its `motif_id`, so packing all member symbols onto the MOTIF line lets a user
# grep any clustered TF (incl. non-representatives) back to the motif_id carrying its PPM.
_SYMBOLS_BY_REP = (
    TF2REP.groupby("Rep_DBID")["TF_Name"]
    .apply(lambda s: ",".join(sorted(set(s.dropna().astype(str)))))
    .to_dict()
)
# A motif's DBID is its representative DBID; fall back to the row's own symbol if unmapped.
ALT_NAMES = {
    row.motif_id: _SYMBOLS_BY_REP.get(row.DBID) or row.TF_Name
    for row in MODES_SORTED.itertuples()
}

TF2REP_BY_DBID = TF2REP.set_index("DBID")


def modes_for_query(dbid):
    """Resolve a searchable entry to its primary and alternate motif rows."""
    if not isinstance(dbid, str) or dbid not in TF2REP_BY_DBID.index:
        return None
    rep = TF2REP_BY_DBID.loc[dbid, "Rep_DBID"]
    return None if pd.isna(rep) else MODES_BY_DBID.get(rep)


# DBID (Ensembl gene ID) -> ZFIN gene ID, from ZFIN's curated 1:1 cross-reference
# (zfin.org/downloads/ensembl_1_to_1.txt). Only ~81% of queryable TFs have a 1:1 ZFIN
# mapping; the rest are absent from this dict and rendered with a dash in the profile.
ZFIN_BY_DBID = TF2REP.dropna(subset=["zfin_id"]).set_index("DBID")["zfin_id"].to_dict()

# Representative DBID -> list of DNA-binding domains, from the InterPro annotations in
# dbd_domains.parquet (exported from af3-tf-motif tfdb4_rep_doms.csv). A rep can have several
# domains (e.g. arrays of C2H2 zinc fingers), so each is a `(start, end, description)`
# chain-A author residue range used by the viewer's domain-only filter.
_DOMAINS = pd.read_parquet(f"{DATA_DIR}/dbd_domains.parquet", engine="pyarrow")
_DBD = _DOMAINS.loc[_DOMAINS["DNA-Binding"]]
DBD_BY_DBID = {}
for r in _DBD.itertuples():
    DBD_BY_DBID.setdefault(r.DBID, []).append((int(r.start), int(r.end), r.description))

# Explain an unavailable domain filter using all annotations, rather than the DBD subset.
# Key by the modeled protein so clustered queries describe the structure being shown.
ANNOTATED_DBIDS = frozenset(_DOMAINS["DBID"])
DOMAIN_STATUS_BY_DBID = {
    dbid: (
        "No domains annotated"
        if dbid not in ANNOTATED_DBIDS
        else "No domains confidently placed with DNA"
        if dbid not in DBD_BY_DBID
        else None
    )
    for dbid in MODES_BY_DBID
}

# Representative DBID -> {chain-A author residue number: contact_mode}, from
# interface_residues.parquet. Each row is a residue that contacts DNA across the sampled
# AF3 models, tagged by what it reaches: a base edge (sequence-specific readout), the
# phosphate backbone (non-specific), or both ("mixed"). Powers the "Show DNA contacts"
# view in the structure viewer. Keyed by representative DBID, matching the loaded structure.
_INTERFACE = pd.read_parquet(f"{DATA_DIR}/interface_residues.parquet", engine="pyarrow")
CONTACTS_BY_DBID = {
    dbid: dict(zip(sub["residue_num"].astype(int), sub["contact_mode"].astype(str)))
    for dbid, sub in _INTERFACE.groupby("DBID")
}

# Confidence is exported per protein, pooled across the top-ranked predictions rather
# than assigned to individual binding-mode clusters. Keep the selected subset explicit.
_CONFIDENCE = pd.read_parquet(
    f"{DATA_DIR}/confidence_metrics.parquet", engine="pyarrow"
)
CONFIDENCE_BY_DBID = {
    dbid: sub.set_index("metric").to_dict("index")
    for dbid, sub in _CONFIDENCE[_CONFIDENCE["subset"] == "top47"].groupby("DBID")
}


# Dropdown options: one per queryable DBID, searchable by gene symbol.
_OPTS = TF2REP.sort_values(["TF_Name", "DBID"])
DROPDOWN_OPTIONS = [
    {
        "label": f"{display_tf_name(r.TF_Name)}  ·  {r.DBID}",
        "value": r.DBID,
        "search": r.TF_Name,
    }
    for r in _OPTS.itertuples()
]


# Database statistics, computed once from the installed tables for page summaries.
N_TFS = TF2REP.loc[TF2REP["in_original_catalog"], "DBID"].nunique()
N_MODELED_SEQUENCES = PRIMARY_MODES["DBID"].nunique()
N_MODES = len(ALL_MODES)  # primary + alternate binding modes
N_FAMILIES = TF2REP["Family"].nunique()
# Count modeled TFs with a reference, including TFs sharing the same ortholog motif.
N_TFS_WITH_JASPAR = PRIMARY_MODES.loc[
    PRIMARY_MODES["hom_jaspar"].notna(), "DBID"
].nunique()

N_PRIMARY = len(PRIMARY_MODES)
N_ALL = len(ALL_MODES)
N_ALT = N_ALL - N_PRIMARY
DOWNLOADS = MotifDownloads(
    {"primary": PRIMARY_MODES, "all": ALL_MODES},
    TF2REP,
    ALT_NAMES,
    DATA_DIR,
    RELEASE_METADATA,
)

METHODS_COUNTS = {
    "catalog_genes": int(N_TFS),
    "query_entries": len(TF2REP),
    "resolved_queries": int(TF2REP["Rep_DBID"].notna().sum()),
    "primary_modes": len(PRIMARY_MODES),
    "alternate_modes": len(ALL_MODES) - len(PRIMARY_MODES),
    "domain_entries": int(TF2REP["sequence_type"].eq("domain").sum()),
    "confidence_proteins": len(CONFIDENCE_BY_DBID),
}
