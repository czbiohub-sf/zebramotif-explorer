import hashlib
import io
import json
import os
import stat
import tempfile
import traceback
import unittest
import warnings
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.response import addinfourl

from zebramotif import dataset


class DatasetInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.archive = self.root / dataset.ARCHIVE_NAME
        self.target = self.root / "cache" / dataset.DATASET_VERSION
        self.secret = "test-preview-secret-that-must-not-leak"
        self.share_url = (
            f"https://zenodo.org/records/{dataset.ZENODO_RECORD}"
            f"?preview=1&token={self.secret}"
        )
        environment = patch.dict(
            os.environ,
            {"ZEBRAMOTIF_ZENODO_URL": "", "ZEBRAMOTIF_ZENODO_URL_FILE": ""},
        )
        environment.start()
        self.addCleanup(environment.stop)
        self.files = {
            name: f"exported {name}\n".encode() for name in dataset.REQUIRED_FILES
        }
        self.files["release_metadata.json"] = json.dumps(
            {"version": dataset.DATASET_VERSION, "doi": "10.5281/zenodo.23380219"}
        ).encode()
        self.files["structures/ZM1.1.cif.gz"] = b"structure bytes"

    def make_archive(self, *, missing=(), changed=None, extra=(), version=None):
        files = {
            name: content for name, content in self.files.items() if name not in missing
        }
        if version is not None:
            files["release_metadata.json"] = json.dumps({"version": version}).encode()
        manifest = "".join(
            f"{hashlib.sha256(content).hexdigest()}  {name}\n"
            for name, content in sorted(files.items())
        ).encode()
        with zipfile.ZipFile(self.archive, "w") as archive:
            for name, content in files.items():
                archive.writestr(name, (changed or {}).get(name, content))
            archive.writestr("SHA256SUMS", manifest)
            for name, content in extra:
                archive.writestr(name, content)
        self.write_archive_checksum()
        return self.archive

    def write_archive_checksum(self):
        self.archive.with_name(self.archive.name + ".sha256").write_text(
            f"{hashlib.sha256(self.archive.read_bytes()).hexdigest()}  {dataset.ARCHIVE_NAME}\n"
        )

    def test_local_export_installs_exact_files_and_verifies_without_network(self):
        self.make_archive()
        with patch(
            "zebramotif.dataset.urlopen", side_effect=AssertionError("network access")
        ):
            result = dataset.install_dataset(self.target, archive=self.archive)
            metadata = dataset.verify_dataset(result)
        self.assertEqual(result, self.target)
        self.assertEqual(metadata["version"], "0.1")
        for name, content in self.files.items():
            self.assertEqual((result / name).read_bytes(), content)

    def test_download_uses_the_pinned_record_archive_and_checksum(self):
        self.make_archive()
        responses = [
            io.BytesIO(
                self.archive.with_name(self.archive.name + ".sha256").read_bytes()
            ),
            io.BytesIO(self.archive.read_bytes()),
        ]
        with patch("zebramotif.dataset.urlopen", side_effect=responses) as download:
            dataset.install_dataset(self.target)
        self.assertEqual(
            [call.args[0].full_url for call in download.call_args_list],
            [
                "https://zenodo.org/records/23380219/files/zebramotif-data-0.1.zip.sha256?download=1",
                "https://zenodo.org/records/23380219/files/zebramotif-data-0.1.zip?download=1",
            ],
        )
        self.assertEqual(
            (self.target / "pwm_modes.parquet").read_bytes(),
            self.files["pwm_modes.parquet"],
        )

    def test_default_cache_and_explicit_directory_are_shared_by_app_and_installer(self):
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(self.root)}, clear=True):
            self.assertEqual(dataset.data_directory(), self.root / "zebramotif/0.1")
        with patch.dict(os.environ, {"ZEBRAMOTIF_DATA_DIR": str(self.target)}):
            self.make_archive()
            dataset.install_dataset(archive=self.archive)
            with patch(
                "zebramotif.dataset.urlopen",
                side_effect=AssertionError("network access"),
            ):
                self.assertEqual(dataset.require_data_directory(), self.target)

    def test_restricted_download_authenticates_once_and_reuses_memory_only_cookies(
        self,
    ):
        self.make_archive()
        secret_file = self.root / "share-url"
        secret_file.write_text(self.share_url + "\n")
        requests = []

        def respond(request):
            requests.append(request)
            headers = Message()
            if len(requests) == 1:
                self.assertEqual(request.full_url, self.share_url)
                headers["Set-Cookie"] = (
                    "session=private-session; Path=/; Secure; HttpOnly"
                )
                content = b"Preview page, never saved"
            else:
                self.assertEqual(
                    request.get_header("Cookie"), "session=private-session"
                )
                self.assertNotIn(self.secret, request.full_url)
                self.assertIsNone(request.get_header("Referer"))
                content = (
                    self.archive.with_name(self.archive.name + ".sha256").read_bytes()
                    if request.full_url.split("?")[0].endswith(".sha256")
                    else self.archive.read_bytes()
                )
            response = addinfourl(io.BytesIO(content), headers, request.full_url, 200)
            response.msg = "OK"
            return response

        output = io.StringIO()
        with (
            patch("urllib.request.HTTPSHandler.https_open", side_effect=respond),
            redirect_stdout(output),
        ):
            dataset.install_dataset(self.target, zenodo_url_file=secret_file)
        self.assertEqual(len(requests), 3)
        self.assertNotIn(self.secret, output.getvalue())
        self.assertEqual(
            requests[1].full_url,
            "https://zenodo.org/records/23380219/files/"
            "zebramotif-data-0.1.zip.sha256?download=1&preview=1",
        )
        self.assertEqual(
            requests[2].full_url,
            "https://zenodo.org/records/23380219/files/"
            "zebramotif-data-0.1.zip?download=1&preview=1",
        )
        for path in self.target.rglob("*"):
            if path.is_file():
                self.assertNotIn(self.secret.encode(), path.read_bytes())
                self.assertNotIn(b"private-session", path.read_bytes())
        self.assertEqual(list(self.target.parent.iterdir()), [self.target])
        dataset.verify_dataset(self.target)

    def test_share_url_sources_support_environment_and_mounted_secret_file(self):
        secret_file = self.root / "share-url"
        secret_file.write_text(self.share_url + "\n")
        with patch.dict(os.environ, {"ZEBRAMOTIF_ZENODO_URL": self.share_url}):
            self.assertEqual(
                dataset._share_url(dataset.ZENODO_RECORD, None), self.share_url
            )
        with patch.dict(
            os.environ,
            {
                "ZEBRAMOTIF_ZENODO_URL_FILE": str(secret_file),
                "ZEBRAMOTIF_ZENODO_URL": "unused-invalid-url",
            },
        ):
            self.assertEqual(
                dataset._share_url(dataset.ZENODO_RECORD, None), self.share_url
            )
        with patch.dict(os.environ, {"ZEBRAMOTIF_ZENODO_URL_FILE": "/nonexistent"}):
            self.assertEqual(
                dataset._share_url(dataset.ZENODO_RECORD, secret_file), self.share_url
            )

    def test_malformed_or_wrong_record_share_urls_never_reach_the_network(self):
        for url in [
            self.share_url.replace("https:", "http:"),
            self.share_url.replace("zenodo.org", "zenodo.org.evil.invalid"),
            self.share_url.replace("zenodo.org", "zenodo.org@evil.invalid"),
            self.share_url.replace("zenodo.org", "user:password@zenodo.org"),
            self.share_url.replace("23380219", "23380220"),
            self.share_url + "&token=another-token",
            self.share_url + "&unrecognized=value",
            self.share_url + "#fragment",
            self.share_url + "\nnew-line",
            self.share_url.replace("preview=1", "preview=0"),
            self.share_url.replace(self.secret, ""),
            "https://[invalid/" + self.secret,
        ]:
            with (
                self.subTest(url=url),
                patch.dict(os.environ, {"ZEBRAMOTIF_ZENODO_URL": url}),
                patch("zebramotif.dataset.build_opener") as opener,
                patch("zebramotif.dataset.urlopen") as download,
            ):
                with self.assertRaisesRegex(
                    ValueError, "Expected an HTTPS Zenodo"
                ) as error:
                    dataset.install_dataset(self.target)
                self.assertNotIn(self.secret, str(error.exception))
                opener.assert_not_called()
                download.assert_not_called()
                self.assertFalse(self.target.exists())

    def test_empty_secret_file_fails_instead_of_attempting_anonymous_access(self):
        secret_file = self.root / "share-url"
        secret_file.write_text("\n")
        with patch("zebramotif.dataset.urlopen") as download:
            with self.assertRaisesRegex(ValueError, "secret file is empty"):
                dataset.install_dataset(self.target, zenodo_url_file=secret_file)
        download.assert_not_called()

    def test_unreadable_secret_paths_are_not_echoed_in_errors(self):
        for filename in (self.root / self.secret, self.share_url):
            with (
                self.subTest(filename_type=type(filename).__name__),
                patch.dict(os.environ, {"ZEBRAMOTIF_ZENODO_URL_FILE": str(filename)}),
                patch("zebramotif.dataset.build_opener") as opener,
            ):
                try:
                    dataset.install_dataset(self.target)
                except ValueError:
                    formatted = traceback.format_exc()
                else:
                    self.fail("Expected an unreadable secret file failure")
                self.assertIn("Cannot read the Zenodo share URL secret file", formatted)
                self.assertNotIn(self.secret, formatted)
                opener.assert_not_called()

    def test_restricted_session_rejects_external_and_insecure_redirects(self):
        for destination in [
            "https://evil.invalid/collect",
            "http://zenodo.org/records/23380219",
            "https://zenodo.org@evil.invalid/collect",
        ]:
            requests = []

            def redirect(request):
                requests.append(request)
                headers = Message()
                headers["Location"] = destination
                headers["Set-Cookie"] = "session=private-session; Path=/; Secure"
                response = addinfourl(io.BytesIO(), headers, request.full_url, 302)
                response.msg = "Found"
                return response

            with (
                self.subTest(destination=destination),
                patch.dict(os.environ, {"ZEBRAMOTIF_ZENODO_URL": self.share_url}),
                patch("urllib.request.HTTPSHandler.https_open", side_effect=redirect),
            ):
                with self.assertRaisesRegex(ValueError, "redirected outside"):
                    dataset.install_dataset(self.target)
                self.assertEqual(len(requests), 1)
                self.assertFalse(self.target.exists())

    def test_network_errors_and_cli_output_do_not_disclose_the_secret(self):
        for error in [
            HTTPError(self.share_url, code, self.share_url, {}, None)
            for code in (401, 403, 404, 500)
        ] + [URLError(self.share_url), TimeoutError(self.share_url)]:
            with (
                self.subTest(error_type=type(error).__name__),
                patch("zebramotif.dataset.urlopen", side_effect=error),
            ):
                try:
                    dataset._download(self.share_url, self.root / "download")
                except ValueError:
                    formatted = traceback.format_exc()
                else:
                    self.fail("Expected a sanitized download failure")
                self.assertNotIn(self.secret, formatted)
        output = io.StringIO()
        with (
            patch.dict(
                os.environ, {"ZEBRAMOTIF_ZENODO_URL": self.share_url + "&bad=1"}
            ),
            redirect_stderr(output),
            self.assertRaises(SystemExit) as error,
        ):
            dataset.main(["--data-dir", str(self.target)])
        self.assertEqual(error.exception.code, 1)
        self.assertNotIn(self.secret, output.getvalue())

    def test_cached_and_local_installs_do_not_need_a_valid_or_present_secret(self):
        self.make_archive()
        with patch.dict(
            os.environ,
            {"ZEBRAMOTIF_ZENODO_URL_FILE": str(self.root / "missing-secret")},
        ):
            dataset.install_dataset(self.target, archive=self.archive)
            with patch(
                "zebramotif.dataset.urlopen", side_effect=AssertionError("network")
            ):
                dataset.install_dataset(self.target)
                dataset.main(["--check", "--data-dir", str(self.target)])
            with patch.dict(os.environ, {"ZEBRAMOTIF_DATA_DIR": str(self.target)}):
                self.assertEqual(dataset.require_data_directory(), self.target)

    def test_missing_data_has_actionable_setup_instructions_without_downloading(self):
        with patch.dict(os.environ, {"ZEBRAMOTIF_DATA_DIR": str(self.target)}):
            with patch(
                "zebramotif.dataset.urlopen",
                side_effect=AssertionError("network access"),
            ):
                with self.assertRaisesRegex(
                    FileNotFoundError, "python -m zebramotif.dataset"
                ):
                    dataset.require_data_directory()

    def test_existing_valid_installation_is_retained_without_network(self):
        self.make_archive()
        dataset.install_dataset(self.target, archive=self.archive)
        path = self.target / "pwm_modes.parquet"
        before = path.stat().st_mtime_ns
        with patch(
            "zebramotif.dataset.urlopen", side_effect=AssertionError("network access")
        ):
            dataset.install_dataset(self.target)
        self.assertEqual(path.stat().st_mtime_ns, before)

    def test_existing_unrelated_files_are_preserved(self):
        self.make_archive()
        self.target.mkdir(parents=True)
        (self.target / "keep.txt").write_text("keep me")
        with self.assertRaises(OSError):
            dataset.install_dataset(self.target, archive=self.archive)
        self.assertEqual((self.target / "keep.txt").read_text(), "keep me")

    def test_archive_checksum_failure_never_installs_partial_data(self):
        self.make_archive()
        self.archive.write_bytes(self.archive.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "ZIP checksum mismatch"):
            dataset.install_dataset(self.target, archive=self.archive)
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.target.parent.iterdir()), [])

    def test_member_checksum_failure_never_installs_partial_data(self):
        self.make_archive(changed={"pwm_modes.parquet": b"changed"})
        with self.assertRaisesRegex(ValueError, "checksum mismatch: pwm_modes.parquet"):
            dataset.install_dataset(self.target, archive=self.archive)
        self.assertFalse(self.target.exists())

    def test_missing_required_file_and_wrong_version_are_rejected(self):
        cases = [
            ({"missing": {"confidence_metrics.parquet"}}, "Incomplete dataset"),
            ({"version": "2.0"}, "Expected dataset version 0.1"),
        ]
        for arguments, message in cases:
            with self.subTest(arguments=arguments):
                self.make_archive(**arguments)
                with self.assertRaisesRegex(ValueError, message):
                    dataset.install_dataset(self.target, archive=self.archive)
                self.assertFalse(self.target.exists())

    def test_unlisted_files_traversal_absolute_paths_and_symlinks_are_rejected(self):
        for name in [
            "extra.txt",
            "../outside.txt",
            "/outside.txt",
            "C:/outside.txt",
            "a\\outside.txt",
        ]:
            with self.subTest(name=name):
                self.make_archive(extra=[(name, b"unexpected")])
                with self.assertRaises(ValueError):
                    dataset.install_dataset(self.target, archive=self.archive)
                self.assertFalse(self.target.exists())
        self.make_archive()
        with zipfile.ZipFile(self.archive, "a") as archive:
            link = zipfile.ZipInfo("link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, "../outside.txt")
        self.write_archive_checksum()
        with self.assertRaisesRegex(ValueError, "not a regular file"):
            dataset.install_dataset(self.target, archive=self.archive)
        self.assertFalse((self.root / "outside.txt").exists())

    def test_duplicate_members_and_duplicate_checksums_are_rejected(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.make_archive(extra=[("pwm_modes.parquet", b"duplicate")])
        with self.assertRaisesRegex(ValueError, "Duplicate dataset ZIP member"):
            dataset.install_dataset(self.target, archive=self.archive)
        self.make_archive()
        with zipfile.ZipFile(self.archive) as archive:
            contents = {name: archive.read(name) for name in archive.namelist()}
        contents["SHA256SUMS"] += contents["SHA256SUMS"].splitlines(keepends=True)[0]
        with zipfile.ZipFile(self.archive, "w") as archive:
            for name, content in contents.items():
                archive.writestr(name, content)
        self.write_archive_checksum()
        with self.assertRaisesRegex(ValueError, "Duplicate checksum entry"):
            dataset.install_dataset(self.target, archive=self.archive)

    def test_verification_detects_changed_or_extra_files_and_wrong_version(self):
        self.make_archive()
        dataset.install_dataset(self.target, archive=self.archive)
        path = self.target / "pwm_modes.parquet"
        path.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "checksum mismatch: pwm_modes.parquet"):
            dataset.verify_dataset(self.target)
        path.write_bytes(self.files["pwm_modes.parquet"])
        (self.target / "extra.txt").write_text("extra")
        with self.assertRaisesRegex(ValueError, "files do not match"):
            dataset.verify_dataset(self.target)

    def test_unpublished_record_and_network_failures_leave_no_installation(self):
        for error, message in [
            (
                HTTPError("https://zenodo.org", 404, "Not Found", {}, None),
                "not publicly available",
            ),
            (URLError("connection interrupted"), "Zenodo download failed"),
        ]:
            with self.subTest(error=error):
                with patch("zebramotif.dataset.urlopen", side_effect=error):
                    with self.assertRaisesRegex(ValueError, message):
                        dataset.install_dataset(self.target)
                self.assertFalse(self.target.exists())

    def test_check_is_read_only_and_invalid_record_is_rejected_before_download(self):
        self.make_archive()
        dataset.install_dataset(self.target, archive=self.archive)
        before = {
            path.relative_to(self.target): path.stat().st_mtime_ns
            for path in self.target.rglob("*")
            if path.is_file()
        }
        with patch(
            "zebramotif.dataset.urlopen", side_effect=AssertionError("network access")
        ):
            dataset.main(["--check", "--data-dir", str(self.target)])
            with self.assertRaisesRegex(ValueError, "numeric record ID"):
                dataset.install_dataset(self.target, record="../../other")
        after = {
            path.relative_to(self.target): path.stat().st_mtime_ns
            for path in self.target.rglob("*")
            if path.is_file()
        }
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
