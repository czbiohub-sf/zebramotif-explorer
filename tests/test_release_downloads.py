import base64
import hashlib
import io
import json
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import dash
import numpy as np
import pandas as pd

import zebramotif.app as dashboard
from zebramotif import data as catalog
from zebramotif.downloads import MotifDownloads
from zebramotif.pages import downloads as download_page
from zebramotif.utils import as_pwm


class ReleaseDownloadTests(unittest.TestCase):
    def setUp(self):
        self.client = dashboard.server.test_client()
        self.downloads = catalog.DOWNLOADS
        self.prefix = f"/downloads/{self.downloads.version}"

    def test_versioned_meme_collections_match_bundled_research_records(self):
        for collection in ("primary", "all"):
            with self.subTest(collection=collection):
                response = self.client.get(f"{self.prefix}/{collection}.meme")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, "text/plain")
                filename = f"zebramotif_{collection}_modes.meme"

                def records(document):
                    return {
                        block.split(maxsplit=1)[0]: block.strip()
                        for block in document.split("\nMOTIF ")[1:]
                    }

                self.assertEqual(
                    records(response.get_data(as_text=True)),
                    records((Path(catalog.DATA_DIR) / filename).read_text()),
                )
                self.assertEqual(
                    response.headers["Content-Disposition"],
                    f'attachment; filename="{filename}"',
                )

    def test_metadata_preserves_all_queries_and_exact_resolution(self):
        queries = catalog.TF2REP.set_index("DBID")
        for collection, modes in self.downloads.collections.items():
            with self.subTest(collection=collection):
                response = self.client.get(f"{self.prefix}/{collection}.metadata.tsv")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, "text/tab-separated-values")
                metadata = pd.read_csv(
                    io.StringIO(response.get_data(as_text=True)),
                    sep="\t",
                    dtype={"release_version": str},
                )
                self.assertEqual(set(metadata["query_dbid"]), set(queries.index))
                self.assertEqual(
                    set(metadata["release_version"]), {self.downloads.version}
                )
                self.assertEqual(
                    set(metadata["motif_id"].dropna()), set(modes["motif_id"])
                )
                counts = queries["Rep_DBID"].map(modes.groupby("DBID").size()).fillna(1)
                actual_counts = (
                    metadata.groupby("query_dbid").size().reindex(queries.index)
                )
                np.testing.assert_array_equal(
                    actual_counts.to_numpy(), counts.to_numpy()
                )
                for column, query_column in [
                    ("query_tf_name", "TF_Name"),
                    ("query_family", "Family"),
                    ("query_sequence_type", "sequence_type"),
                    ("representative_dbid", "Rep_DBID"),
                    ("resolution", "resolution"),
                    ("query_is_representative", "is_representative"),
                    ("in_original_catalog", "in_original_catalog"),
                    ("zfin_id", "zfin_id"),
                ]:
                    actual = metadata.drop_duplicates("query_dbid").set_index(
                        "query_dbid"
                    )[column]
                    pd.testing.assert_series_equal(
                        actual.reindex(queries.index),
                        queries[query_column],
                        check_dtype=False,
                        check_names=False,
                    )
                unresolved = metadata[metadata["representative_dbid"].isna()]
                self.assertEqual(len(unresolved), queries["Rep_DBID"].isna().sum())
                self.assertTrue(unresolved["motif_id"].isna().all())

    def test_metadata_preserves_raw_metrics_mode_identity_and_sequence_type(self):
        for collection, modes in self.downloads.collections.items():
            with self.subTest(collection=collection):
                metadata = (
                    pd.read_csv(
                        io.StringIO(self.downloads.metadata_tsv(collection)),
                        sep="\t",
                        float_precision="round_trip",
                    )
                    .dropna(subset=["motif_id"])
                    .drop_duplicates("motif_id")
                    .set_index("motif_id")
                )
                expected = modes.set_index("motif_id").loc[metadata.index]
                for column in [
                    "mode_rank",
                    "n_members",
                    "num_specs",
                    "cor_threshold",
                    "pwm_length",
                    "corr_to_primary",
                    "offset_to_primary",
                    "hom_sim",
                    "homer_sim",
                    "z_score",
                    "p_value",
                    "recovery",
                ]:
                    np.testing.assert_allclose(
                        metadata[column].to_numpy(dtype=float),
                        expected[column].to_numpy(dtype=float),
                        rtol=0,
                        atol=0,
                        equal_nan=True,
                        err_msg=column,
                    )
                for column, mode_column in [
                    ("representative_dbid", "DBID"),
                    ("representative_tf_name", "TF_Name"),
                    ("representative_family", "Family"),
                    ("representative_sequence_type", "sequence_type"),
                    ("tier", "tier"),
                    ("hom_jaspar", "hom_jaspar"),
                ]:
                    pd.testing.assert_series_equal(
                        metadata[column],
                        expected[mode_column],
                        check_dtype=False,
                        check_names=False,
                    )
                actual_rc = metadata["rc_to_primary"].fillna("").astype(str)
                expected_rc = expected["rc_to_primary"].fillna("").astype(str)
                pd.testing.assert_series_equal(
                    actual_rc, expected_rc, check_names=False
                )
                self.assertEqual(
                    metadata["meme_name"].to_dict(),
                    {
                        motif_id: catalog.ALT_NAMES[motif_id]
                        for motif_id in metadata.index
                    },
                )

    def test_archives_contain_every_matrix_and_preserved_release_notices(self):
        data_dir = Path(catalog.DATA_DIR)
        for collection, modes in self.downloads.collections.items():
            with self.subTest(collection=collection):
                response = self.client.get(f"{self.prefix}/{collection}.zip")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, "application/zip")
                with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
                    files = archive.namelist()
                    self.assertEqual(len(files), len(set(files)))
                    checksums = {
                        name: digest
                        for digest, name in (
                            line.split("  ", maxsplit=1)
                            for line in archive.read("SHA256SUMS").decode().splitlines()
                        )
                    }
                    self.assertEqual(set(checksums), set(files) - {"SHA256SUMS"})
                    for name, digest in checksums.items():
                        self.assertEqual(
                            hashlib.sha256(archive.read(name)).hexdigest(), digest
                        )
                    self.assertEqual(
                        {
                            name.removesuffix(".meme")
                            for name in files
                            if name.endswith(".meme")
                        },
                        set(modes["motif_id"]),
                    )
                    self.assertEqual(
                        archive.read("metadata.tsv").decode(),
                        self.downloads.metadata_tsv(collection),
                    )
                    self.assertEqual(
                        json.loads(archive.read("release_metadata.json")),
                        catalog.RELEASE_METADATA,
                    )
                    self.assertIn(
                        self.downloads.version, archive.read("README.md").decode()
                    )
                    for name, source in [
                        ("dataset_README.md", "README.md"),
                        ("LICENSE.md", "LICENSE.md"),
                        (
                            "Legally Binding Terms of Use.txt",
                            "Legally Binding Terms of Use.txt",
                        ),
                        ("CITATION.cff", "CITATION.cff"),
                        ("PROVENANCE.json", "PROVENANCE.json"),
                    ]:
                        self.assertEqual(
                            archive.read(name), (data_dir / source).read_bytes()
                        )
                    for notice in (data_dir / "notices").rglob("*"):
                        if notice.is_file():
                            self.assertEqual(
                                archive.read(notice.relative_to(data_dir).as_posix()),
                                notice.read_bytes(),
                            )
                    for _, mode in modes.iterrows():
                        document = archive.read(f"{mode['motif_id']}.meme").decode()
                        self.assertTrue(document.startswith("MEME version 4\n"))
                        self.assertEqual(document.count("\nMOTIF "), 1)
                        self.assertIn(
                            f"MOTIF {mode['motif_id']} {catalog.ALT_NAMES[mode['motif_id']]}\n",
                            document,
                        )
                        lines = document.splitlines()
                        start = next(
                            i
                            for i, line in enumerate(lines)
                            if line.startswith("letter-probability matrix:")
                        )
                        self.assertIn(f"nsites= {mode['n_members']}", lines[start])
                        np.testing.assert_allclose(
                            np.loadtxt(lines[start + 1 :], ndmin=2),
                            as_pwm(mode["pwm"]),
                            rtol=0,
                            atol=5e-7,
                        )

    def test_archive_bytes_are_deterministic_without_using_cache(self):
        modes = catalog.MODES_BY_DBID["ENSDARG00000013279"]
        queries = catalog.TF2REP[catalog.TF2REP["Rep_DBID"].eq("ENSDARG00000013279")]
        downloads = MotifDownloads(
            {"primary": modes[modes["tier"].eq("primary")], "all": modes},
            queries,
            catalog.ALT_NAMES,
            catalog.DATA_DIR,
            catalog.RELEASE_METADATA,
        )
        first, second = io.BytesIO(), io.BytesIO()
        downloads.write_zip(first, "all")
        downloads.write_zip(second, "all")
        self.assertEqual(first.getvalue(), second.getvalue())

    def test_button_callbacks_match_direct_downloads_and_preserve_sinks(self):
        controls = [
            ("btn-primary-batch", "primary", "meme"),
            ("btn-primary-zip", "primary", "zip"),
            ("btn-all-batch", "all", "meme"),
            ("btn-all-zip", "all", "zip"),
        ]
        for index, (button, collection, extension) in enumerate(controls):
            with (
                self.subTest(button=button),
                patch("zebramotif.pages.downloads.ctx") as context,
            ):
                context.triggered_id = button
                result = download_page.handle_download(1, 1, 1, 1)
                self.assertEqual(len(result), 4)
                for other in range(4):
                    if other != index:
                        self.assertIs(result[other], dash.no_update)
                attachment = result[index]
                body = (
                    base64.b64decode(attachment["content"])
                    if attachment["base64"]
                    else attachment["content"].encode()
                )
                endpoint = self.client.get(f"{self.prefix}/{collection}.{extension}")
                self.assertEqual(body, endpoint.data)
                self.assertEqual(
                    attachment["filename"],
                    self.downloads.filename(collection, extension),
                )

    def test_release_metadata_and_head_are_supported(self):
        response = self.client.get(f"{self.prefix}/release_metadata.json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), catalog.RELEASE_METADATA)
        for collection in ("primary", "all"):
            for extension in ("meme", "zip"):
                with self.subTest(collection=collection, extension=extension):
                    path = f"{self.prefix}/{collection}.{extension}"
                    response = self.client.head(
                        path, headers={"Accept-Encoding": "gzip, br"}
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.data, b"")
                    downloaded = self.client.get(path)
                    size = len(downloaded.data)
                    self.assertEqual(response.headers["X-File-Size"], str(size))
                    self.assertEqual(downloaded.headers["X-File-Size"], str(size))
                    self.assertEqual(
                        self.client.head(
                            path, headers={"Accept-Encoding": "identity"}
                        ).content_length,
                        size,
                    )

    def test_unknown_versions_files_and_path_traversal_are_rejected(self):
        for path in [
            "/downloads/1900.01.01/primary.meme",
            f"{self.prefix}/missing.meme",
            f"{self.prefix}/pwm_modes.parquet",
            f"{self.prefix}/../LICENSE.md",
            f"{self.prefix}/%2e%2e%2fLICENSE.md",
            f"{self.prefix}/%2Fetc%2Fpasswd",
            f"{self.prefix}/notices/AF3_OUTPUT_TERMS_OF_USE.md",
        ]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(
            self.client.post(f"{self.prefix}/primary.meme").status_code, 405
        )


if __name__ == "__main__":
    unittest.main()
