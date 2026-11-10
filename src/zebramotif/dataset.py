"""Install the versioned dataset exported by af3-tf-motif from Zenodo."""

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from http.client import HTTPException
from http.cookiejar import CookieJar
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import (
    HTTPCookieProcessor,
    HTTPRedirectHandler,
    Request,
    build_opener,
    urlopen,
)

DATASET_VERSION = "0.1"
ZENODO_RECORD = "23380219"
ARCHIVE_NAME = f"zebramotif-data-{DATASET_VERSION}.zip"
REQUIRED_FILES = frozenset(
    {
        "pwm_modes.parquet",
        "tf_to_rep.parquet",
        "confidence_metrics.parquet",
        "interface_residues.parquet",
        "dbd_domains.parquet",
        "zebramotif_primary_modes.meme",
        "zebramotif_all_modes.meme",
        "zebramotif_primary_modes.metadata.tsv",
        "zebramotif_all_modes.metadata.tsv",
        "SCHEMA.md",
        "release_metadata.json",
        "README.md",
        "LICENSE.md",
        "Legally Binding Terms of Use.txt",
        "CITATION.cff",
        "ZENODO_METADATA.json",
        "PROVENANCE.json",
        "notices/AF3_OUTPUT_TERMS_OF_USE.md",
        "notices/AF3_WEIGHTS_PROHIBITED_USE_POLICY.md",
        "notices/AF3_WEIGHTS_TERMS_OF_USE.md",
        "notices/ZebraMotif-MIT.txt",
        "notices/af3-tf-motif-MIT.txt",
        "notices/sources.json",
    }
)


def data_directory() -> Path:
    """Use an explicit dataset directory or the versioned user cache."""
    configured = os.environ.get("ZEBRAMOTIF_DATA_DIR")
    if configured:
        return Path(configured).expanduser().absolute()
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return cache.expanduser().absolute() / "zebramotif" / DATASET_VERSION


def _check_metadata(directory: Path) -> dict:
    metadata = json.loads((directory / "release_metadata.json").read_text())
    if metadata.get("version") != DATASET_VERSION:
        raise ValueError(
            f"Expected dataset version {DATASET_VERSION}, "
            f"found {metadata.get('version')!r} in {directory}"
        )
    return metadata


def require_data_directory() -> Path:
    """Resolve an installed dataset without networking or hashing it at startup."""
    directory = data_directory()
    missing = [name for name in REQUIRED_FILES if not (directory / name).is_file()]
    if missing or not (directory / "SHA256SUMS").is_file():
        raise FileNotFoundError(
            f"ZebraMotif dataset {DATASET_VERSION} is not installed at {directory}. "
            "Run `python -m zebramotif.dataset` to download it from Zenodo. "
            "Set ZEBRAMOTIF_DATA_DIR to use another installed dataset directory."
        )
    _check_metadata(directory)
    return directory


def _safe_name(name: str) -> str:
    path = PurePosixPath(name)
    if (
        not name
        or not path.parts
        or path.is_absolute()
        or "\\" in name
        or ":" in name
        or ".." in path.parts
        or path.as_posix() != name
        or "\x00" in name
    ):
        raise ValueError(f"Unsafe dataset path: {name!r}")
    return name


def _checksums(document: str) -> dict[str, str]:
    records = {}
    for line in document.splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64})  (.+)", line)
        if match is None:
            raise ValueError("Invalid SHA256SUMS entry")
        digest, name = match.groups()
        _safe_name(name)
        if name in records:
            raise ValueError(f"Duplicate checksum entry: {name}")
        records[name] = digest.lower()
    if not records:
        raise ValueError("Empty SHA256SUMS manifest")
    return records


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def verify_dataset(directory: Path) -> dict:
    """Check every extracted file against the export's own checksum manifest."""
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError(f"Dataset must be a regular directory: {directory}")
    files = set()
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Symlink in dataset: {path}")
        if path.is_file():
            files.add(path.relative_to(directory).as_posix())
    expected = _checksums((directory / "SHA256SUMS").read_text())
    if set(expected) != files - {"SHA256SUMS"}:
        raise ValueError("Dataset files do not match SHA256SUMS")
    if missing := REQUIRED_FILES - files:
        raise ValueError(f"Incomplete dataset; missing: {', '.join(sorted(missing))}")
    for name, digest in expected.items():
        if _sha256(directory / name) != digest:
            raise ValueError(f"Dataset checksum mismatch: {name}")
    return _check_metadata(directory)


def _is_zenodo_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.netloc in {"zenodo.org", "zenodo.org:443"}


class _ZenodoRedirectHandler(HTTPRedirectHandler):
    """Keep the share link and session cookies on Zenodo over verified HTTPS."""

    def redirect_request(self, request, response, code, message, headers, newurl):
        if not _is_zenodo_url(newurl):
            raise ValueError("Zenodo redirected outside https://zenodo.org; stopped.")
        return super().redirect_request(
            request, response, code, message, headers, newurl
        )


def _share_url(record: str, url_file: Path | None) -> str | None:
    """Read a deployment secret only when a remote installation is needed."""
    url_file = url_file or os.environ.get("ZEBRAMOTIF_ZENODO_URL_FILE")
    if url_file:
        try:
            url = Path(url_file).expanduser().read_text(encoding="utf-8").strip()
        except (OSError, ValueError):
            # A mistaken URL in the *_FILE setting must not be echoed as a path.
            raise ValueError(
                "Cannot read the Zenodo share URL secret file. Check its path, "
                "permissions, and UTF-8 encoding; use ZEBRAMOTIF_ZENODO_URL "
                "when supplying the link directly."
            ) from None
        if not url:
            raise ValueError("The Zenodo share URL secret file is empty.")
    else:
        url = os.environ.get("ZEBRAMOTIF_ZENODO_URL", "").strip()
        if not url:
            return None
    # Validate before making any request; never echo a malformed secret in errors.
    message = (
        "Expected an HTTPS Zenodo share URL for the selected record, "
        "with one nonempty token and an optional preview=1 parameter."
    )
    try:
        parts = urlsplit(url)
        query = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True)
        if (
            not _is_zenodo_url(url)
            or parts.path.rstrip("/") != f"/records/{record}"
            or parts.fragment
            or set(query) - {"preview", "token"}
            or len(query.get("token", [])) != 1
            or not query["token"][0]
            or ("preview" in query and query["preview"] != ["1"])
            or any(character.isspace() for character in url)
        ):
            raise ValueError(message)
    except ValueError:
        raise ValueError(message) from None
    # Use our fixed host/path rather than carrying arbitrary URL components forward.
    return f"https://zenodo.org/records/{record}?{urlencode(query, doseq=True)}"


def _download(url: str, target: Path | None = None, *, opener=None) -> None:
    """Download without logging URLs, response bodies, cookies, or exception secrets."""
    request = Request(url, headers={"User-Agent": "ZebraMotif dataset installer/0.1"})
    try:
        open_url = opener.open if opener is not None else urlopen
        with open_url(request, timeout=60) as response:
            if target is not None:
                with target.open("wb") as handle:
                    shutil.copyfileobj(response, handle)
    except HTTPError as error:
        if error.code in {401, 403, 404}:
            raise ValueError(
                "The Zenodo record or release file is not publicly available "
                f"or access was denied (HTTP {error.code}). "
                "For restricted data, set ZEBRAMOTIF_ZENODO_URL_FILE to a secret "
                "file containing a valid share/preview link, or set "
                "ZEBRAMOTIF_ZENODO_URL. Check that the link has not expired or "
                "been revoked. For a local export, use --archive with the ZIP "
                "and its .zip.sha256 file."
            ) from None
        raise ValueError(
            f"Zenodo download failed (HTTP {error.code}); retry the installation."
        ) from None
    except (URLError, TimeoutError, HTTPException):
        raise ValueError(
            "Zenodo download failed; check HTTPS connectivity and retry the installation."
        ) from None


def _extract(archive: Path, directory: Path) -> None:
    """Validate the entire ZIP inventory before extracting regular files."""
    with zipfile.ZipFile(archive) as bundle:
        members = {}
        for member in bundle.infolist():
            name = _safe_name(member.filename)
            mode = member.external_attr >> 16
            if member.is_dir() or stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                raise ValueError(f"Dataset ZIP member is not a regular file: {name}")
            if name in members:
                raise ValueError(f"Duplicate dataset ZIP member: {name}")
            members[name] = member
        if "SHA256SUMS" not in members:
            raise ValueError("Dataset ZIP is missing SHA256SUMS")
        expected = _checksums(bundle.read("SHA256SUMS").decode())
        if set(expected) != set(members) - {"SHA256SUMS"}:
            raise ValueError("Dataset ZIP files do not match SHA256SUMS")
        if missing := REQUIRED_FILES - set(members):
            raise ValueError(
                f"Incomplete dataset ZIP; missing: {', '.join(sorted(missing))}"
            )
        for name, member in members.items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, path.open("wb") as target:
                shutil.copyfileobj(source, target)
            if name != "SHA256SUMS" and _sha256(path) != expected[name]:
                raise ValueError(f"Dataset checksum mismatch: {name}")
    _check_metadata(directory)


def install_dataset(
    directory: Path | None = None,
    *,
    record: str = ZENODO_RECORD,
    archive: Path | None = None,
    zenodo_url_file: Path | None = None,
) -> Path:
    """Install a complete, verified export atomically; retain existing datasets."""
    if not re.fullmatch(r"[1-9][0-9]*", record):
        raise ValueError("Zenodo record must be a numeric record ID")
    directory = Path(directory or data_directory()).expanduser().absolute()
    if directory.is_symlink():
        raise ValueError(f"Dataset directory cannot be a symlink: {directory}")
    if directory.exists():
        if not directory.is_dir():
            raise ValueError(f"Dataset destination is not a directory: {directory}")
        if any(directory.iterdir()):
            verify_dataset(directory)
            print(
                f"Dataset {DATASET_VERSION} is already installed and verified: {directory}"
            )
            return directory
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{directory.name}.download-", dir=directory.parent
    ) as temporary:
        staging = Path(temporary)
        if archive is None:
            archive = staging / ARCHIVE_NAME
            base_url = f"https://zenodo.org/records/{record}/files/"
            checksum_path = staging / f"{ARCHIVE_NAME}.sha256"
            opener = None
            download_query = "download=1"
            if share_url := _share_url(record, zenodo_url_file):
                # Bootstrap the preview link once, then fetch files using only the
                # in-memory cookie jar. Neither cookies nor the link enter the cache.
                opener = build_opener(
                    _ZenodoRedirectHandler(), HTTPCookieProcessor(CookieJar())
                )
                _download(share_url, opener=opener)
                # Unpublished files require the draft selector in addition to the
                # authenticated session; otherwise Zenodo returns a public-file 404.
                if "preview" in parse_qs(urlsplit(share_url).query):
                    download_query += "&preview=1"
            print(
                f"Downloading dataset {DATASET_VERSION} from Zenodo record {record}..."
            )
            _download(
                base_url + f"{ARCHIVE_NAME}.sha256?{download_query}",
                checksum_path,
                opener=opener,
            )
            expected = _checksums(checksum_path.read_text())
            if set(expected) != {ARCHIVE_NAME}:
                raise ValueError(
                    "Archive checksum file does not identify the expected release ZIP"
                )
            _download(
                base_url + f"{ARCHIVE_NAME}?{download_query}", archive, opener=opener
            )
        else:
            archive = Path(archive).expanduser().resolve()
            checksum_path = archive.with_name(archive.name + ".sha256")
            expected = _checksums(checksum_path.read_text())
            if set(expected) != {ARCHIVE_NAME}:
                raise ValueError(
                    "Archive checksum file does not identify the expected release ZIP"
                )
        if _sha256(archive) != expected[ARCHIVE_NAME]:
            raise ValueError("Dataset ZIP checksum mismatch")
        extracted = staging / "dataset"
        extracted.mkdir()
        _extract(archive, extracted)
        if directory.exists():
            if any(directory.iterdir()):
                verify_dataset(directory)
                if (directory / "SHA256SUMS").read_bytes() != (
                    extracted / "SHA256SUMS"
                ).read_bytes():
                    raise ValueError(
                        f"A different dataset was installed concurrently: {directory}"
                    )
                return directory
            directory.rmdir()
        try:
            extracted.rename(directory)
        except OSError:
            if not directory.is_dir():
                raise
            verify_dataset(directory)
            if (directory / "SHA256SUMS").read_bytes() != (
                extracted / "SHA256SUMS"
            ).read_bytes():
                raise ValueError(
                    f"A different dataset was installed concurrently: {directory}"
                )
    print(f"Installed and verified dataset {DATASET_VERSION}: {directory}")
    return directory


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        help="Install directory (default: ZEBRAMOTIF_DATA_DIR or the versioned user cache).",
    )
    parser.add_argument(
        "--record",
        default=ZENODO_RECORD,
        help=f"Zenodo record ID (default: {ZENODO_RECORD}).",
    )
    parser.add_argument(
        "--zenodo-url-file",
        type=Path,
        help=(
            "File containing a restricted Zenodo share/preview URL. Defaults to "
            "ZEBRAMOTIF_ZENODO_URL_FILE, then ZEBRAMOTIF_ZENODO_URL. "
            "The secret is used only for downloads; keep it outside the checkout."
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--archive",
        type=Path,
        help="Install a local export ZIP with its matching .zip.sha256 sidecar.",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="Verify the installed dataset without downloading or changing it.",
    )
    args = parser.parse_args(argv)
    try:
        directory = args.data_dir or data_directory()
        if args.check:
            verify_dataset(directory)
            print(f"Dataset {DATASET_VERSION} files and checksums match: {directory}")
        else:
            install_dataset(
                directory,
                record=args.record,
                archive=args.archive,
                zenodo_url_file=args.zenodo_url_file,
            )
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Dataset installation failed: {error}\n")


if __name__ == "__main__":
    main()
