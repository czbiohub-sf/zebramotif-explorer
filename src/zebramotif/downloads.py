"""Versioned, self-describing motif collection downloads."""

import hashlib
import io
import json
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Literal

from flask import Response, abort

from zebramotif.utils import meme_document

Collection = Literal["primary", "all"]

_MODE_COLUMNS = [
    "DBID",
    "TF_Name",
    "Family",
    "sequence_type",
    "motif_id",
    "tier",
    "mode_rank",
    "n_members",
    "num_specs",
    "cor_threshold",
    "pwm_length",
    "corr_to_primary",
    "offset_to_primary",
    "rc_to_primary",
    "hom_jaspar",
    "hom_sim",
    "homer_sim",
    "z_score",
    "p_value",
    "recovery",
]
_QUERY_NAMES = {
    "DBID": "query_dbid",
    "TF_Name": "query_tf_name",
    "Family": "query_family",
    "sequence_type": "query_sequence_type",
    "Rep_DBID": "representative_dbid",
    "is_representative": "query_is_representative",
}
_MODE_NAMES = {
    "DBID": "representative_dbid",
    "TF_Name": "representative_tf_name",
    "Family": "representative_family",
    "sequence_type": "representative_sequence_type",
}
_METADATA_COLUMNS = [
    "release_version",
    "query_dbid",
    "query_tf_name",
    "query_family",
    "query_sequence_type",
    "representative_dbid",
    "representative_tf_name",
    "representative_family",
    "representative_sequence_type",
    "resolution",
    "query_is_representative",
    "in_original_catalog",
    "zfin_id",
    "motif_id",
    "meme_name",
    "tier",
    "mode_rank",
    "n_members",
    "num_specs",
    "cor_threshold",
    "pwm_length",
    "corr_to_primary",
    "offset_to_primary",
    "rc_to_primary",
    "hom_jaspar",
    "hom_sim",
    "homer_sim",
    "z_score",
    "p_value",
    "recovery",
]
_DOCUMENTS = {
    "dataset_README.md": "README.md",
    "LICENSE.md": "LICENSE.md",
    "Legally Binding Terms of Use.txt": "Legally Binding Terms of Use.txt",
    "CITATION.cff": "CITATION.cff",
    "PROVENANCE.json": "PROVENANCE.json",
}


class MotifDownloads:
    """Use the same matrices, symbol names, and release metadata for every format."""

    def __init__(self, collections, queries, names, data_dir, release_metadata):
        self.collections = collections
        self.queries = queries
        self.names = names
        self.data_dir = Path(data_dir)
        self.release_metadata = release_metadata
        self.version = release_metadata["version"]
        # Each instance owns bounded caches with functools' thread-safe cache updates.
        self.meme = lru_cache(maxsize=2)(self.meme)
        self.metadata_tsv = lru_cache(maxsize=2)(self.metadata_tsv)
        self.archive_bytes = lru_cache(maxsize=2)(self.archive_bytes)

    @staticmethod
    def filename(collection: Collection, extension: str) -> str:
        suffix = "_meme" if extension == "zip" else ""
        return f"zebramotif_{collection}_modes{suffix}.{extension}"

    def meme(self, collection: Collection) -> str:
        return meme_document(self.collections[collection], self.names)

    def metadata_tsv(self, collection: Collection) -> str:
        """One row per query-to-mode mapping; retain unresolved queries explicitly."""
        queries = self.queries.rename(columns=_QUERY_NAMES)
        modes = self.collections[collection][_MODE_COLUMNS].rename(columns=_MODE_NAMES)
        metadata = queries.merge(modes, on="representative_dbid", how="left")
        metadata.insert(0, "release_version", self.version)
        metadata["meme_name"] = (
            metadata["motif_id"]
            .map(self.names)
            .fillna(metadata["representative_tf_name"])
        )
        for column in [
            "mode_rank",
            "n_members",
            "num_specs",
            "pwm_length",
            "offset_to_primary",
        ]:
            metadata[column] = metadata[column].astype("Int64")
        metadata["_tier_order"] = metadata["tier"].map({"primary": 0, "alternate": 1})
        metadata = metadata.sort_values(["query_dbid", "_tier_order", "mode_rank"])
        return metadata[_METADATA_COLUMNS].to_csv(
            sep="\t", index=False, na_rep="", lineterminator="\n"
        )

    def release_json(self) -> str:
        return json.dumps(self.release_metadata, ensure_ascii=False, indent=2) + "\n"

    def readme(self, collection: Collection) -> str:
        rows = self.collections[collection]
        title = "Primary modes" if collection == "primary" else "All modes"
        scope = (
            "One primary binding mode per modeled representative."
            if collection == "primary"
            else "Each modeled representative's primary mode and all alternate modes."
        )
        return f"""# {self.release_metadata["title"]}

## {title}

Dataset version: {self.version}.
{scope} This bundle contains {len(rows):,} predicted DNA-binding probability
matrices for {rows["DBID"].nunique():,} modeled representatives.

## Files and identifiers

- `<motif_id>.meme`: one complete minimal MEME document per binding mode.
- `metadata.tsv`: query TF/DBID → modeled representative → motif ID, sequence
  types, and raw mode metrics. Multiple queries can share a representative and
  motif. There is one row per query-to-mode mapping; unresolved queries are
  retained with empty motif fields. Empty fields indicate missing values.
- `release_metadata.json`: dataset version, methods, sources, and provenance gaps.
- `CITATION.cff`, `LICENSE.md`, `Legally Binding Terms of Use.txt`, and `notices/`:
  existing dataset citation, rights information, and full source terms.
- `dataset_README.md` and `PROVENANCE.json`: original full-dataset documentation
  and provenance. Their inventory describes the full research release; this
  motif-only bundle does not include Parquet tables or protein structures.
- `SHA256SUMS`: SHA-256 checksums of this ZIP's actual members, excluding the
  checksum file itself. The hashes in `PROVENANCE.json` describe the full
  scientific snapshot; use this bundle's `SHA256SUMS` to verify extracted files.

Select motifs in MEME tools by `motif_id`. The MEME alternate name (`meme_name`
in the TSV) lists the sorted, comma-separated gene symbols resolving to the
representative. Matrices use A,C,G,T columns, six decimal places, and uniform
background frequencies. `nsites` is cluster support (`n_members`), rather than
a count of experimentally measured sites. Predictions are not experimental
binding measurements.

## Metadata fields

Read `release_version` as text so values such as `0.1` remain version labels.
`query_*` fields describe the searched TF or separately modeled domain.
`representative_*` fields describe the protein whose sequence was modeled.
Both sequence-type columns use `full_length` or `domain`. `resolution` and
`query_is_representative` preserve the website lookup; `in_original_catalog`
and `zfin_id` annotate the query. `tier` is `primary` or `alternate`; alternate
`mode_rank` runs from 1 to 3 independently of the primary's rank of 1.

Raw values are exported without display rounding:

- `n_members` / `num_specs`: cluster members / selected specificity predictions;
  their ratio is prediction support, not a calibrated probability of correctness.
- `cor_threshold`: UPGMA merge cutoff; `pwm_length`: matrix length in bases.
- `corr_to_primary`, `offset_to_primary`, `rc_to_primary`: alternate-to-primary
  similarity, alignment offset in bases, and reverse-complement flag.
- `hom_jaspar`: cognate JASPAR motif ID; `hom_sim`: DNA-binding domain (DBD)
  similarity in percent, labeled "DBD similarity" on the website.
- `homer_sim`: predicted-to-reference motif similarity (0–1).
- `recovery`: JASPAR information-content-weighted recovery fraction (0–1).
- `z_score`, `p_value`: comparison with the JASPAR null motif set, reported as
  a z score and empirical p value. Missing references remain empty.

## Reuse and citation

Read the accompanying `LICENSE.md`, `Legally Binding Terms of Use.txt`, and
`notices/AF3_OUTPUT_TERMS_OF_USE.md`. They apply the existing dataset policy
to AlphaFold 3 predictions and derivatives; reference annotations retain their
providers' terms. Cite this exact dataset version using `CITATION.cff` and the
AlphaFold 3 paper cited in `LICENSE.md`. See `release_metadata.json` for the
current publication/DOI status and original repository links.

## Direct URLs

The website serves this release at `/downloads/{self.version}/{collection}.meme`,
`/downloads/{self.version}/{collection}.zip`, and
`/downloads/{self.version}/{collection}.metadata.tsv`. Shared release information
is at `/downloads/{self.version}/release_metadata.json`.
"""

    @staticmethod
    def _write_member(archive, filename, payload):
        """Fix timestamps and permissions so repeated archives are byte-identical."""
        info = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.create_system = 3
        info.external_attr = 0o100644 << 16
        archive.writestr(info, payload)

    def write_zip(self, buffer, collection: Collection):
        rows = self.collections[collection]
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            checksums = {}

            def write_member(filename, payload):
                raw = payload.encode("utf-8") if isinstance(payload, str) else payload
                checksums[filename] = hashlib.sha256(raw).hexdigest()
                self._write_member(archive, filename, raw)

            write_member("README.md", self.readme(collection))
            write_member("metadata.tsv", self.metadata_tsv(collection))
            write_member("release_metadata.json", self.release_json())
            for index in range(len(rows)):
                mode = rows.iloc[[index]]
                write_member(
                    f"{mode.iloc[0]['motif_id']}.meme",
                    meme_document(mode, self.names),
                )
            for filename, source in sorted(_DOCUMENTS.items()):
                write_member(filename, (self.data_dir / source).read_bytes())
            for source in sorted((self.data_dir / "notices").rglob("*")):
                if source.is_file():
                    write_member(
                        source.relative_to(self.data_dir).as_posix(),
                        source.read_bytes(),
                    )
            self._write_member(
                archive,
                "SHA256SUMS",
                "".join(f"{checksums[name]}  {name}\n" for name in sorted(checksums)),
            )

    def archive_bytes(self, collection: Collection) -> bytes:
        buffer = io.BytesIO()
        self.write_zip(buffer, collection)
        return buffer.getvalue()


def register_download_routes(server, downloads):
    """Serve whitelisted release assets without mapping request paths to the filesystem."""
    formats = {
        f"{collection}.{extension}": (collection, extension)
        for collection in ("primary", "all")
        for extension in ("meme", "zip", "metadata.tsv")
    }

    @server.get("/downloads/<version>/<filename>")
    def download_release_asset(version, filename):
        if version != downloads.version:
            abort(404)
        if filename == "release_metadata.json":
            return Response(downloads.release_json(), mimetype="application/json")
        if filename not in formats:
            abort(404)
        collection, extension = formats[filename]
        if extension == "meme":
            payload, mimetype = downloads.meme(collection), "text/plain"
        elif extension == "zip":
            payload, mimetype = downloads.archive_bytes(collection), "application/zip"
        else:
            payload, mimetype = (
                downloads.metadata_tsv(collection),
                "text/tab-separated-values",
            )
        response = Response(
            payload,
            mimetype=mimetype,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{downloads.filename(collection, extension)}"'
                ),
            },
        )
        # Preserve the saved file's size when middleware compresses the HTTP response.
        response.headers["X-File-Size"] = str(response.content_length)
        return response
