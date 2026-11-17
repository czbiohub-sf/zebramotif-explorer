# ZebraMotif

An interactive web app for exploring predicted DNA-binding motifs and AlphaFold 3
protein–DNA structures for zebrafish transcription factors.

Developed and maintained by the Royer group at Chan Zuckerberg Biohub San
Francisco. Maintainers: @biovino2 and @royerloic.

**Pre-release.** Public website and dataset links will be added at release.
Until then, dataset access is available from the maintainers.

- Search transcription factors by gene symbol or Ensembl ID.
- Compare primary and alternate binding motifs with JASPAR ortholog motifs.
- Explore 3D structures, DNA-binding domains, DNA contacts, and confidence scores.
- Download motifs and metadata, or share a link to a selected transcription factor.

The app's **Methods & Cite** page explains the methods, metrics, and citations.

## Run locally

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).
Dependencies are declared in [pyproject.toml](pyproject.toml) and pinned in
[uv.lock](uv.lock).
Until release, ask the maintainers for dataset access. Save the authorized
Zenodo share/preview URL in a private file outside this checkout, then set
`ZEBRAMOTIF_ZENODO_URL_FILE` to its path. Keep this URL private. After the
record is public, no access file is needed.

```bash
uv sync --frozen
uv run python -m zebramotif.dataset
uv run zebramotif
```

Open http://localhost:8099. The dataset downloads once and is cached locally.
Set `ZEBRAMOTIF_PORT` to use another port. Set `ZEBRAMOTIF_DATA_DIR` to use
a specific dataset directory. To install an archive supplied by the maintainers,
place `zebramotif-data-0.1.zip` and its matching `.zip.sha256` file together,
then run `uv run python -m zebramotif.dataset --archive /path/to/zebramotif-data-0.1.zip`.
Run `uv run python -m zebramotif.dataset --check` to verify the installed files.
See the [Argus deployment guide](deploy/argus.md) for the public website and the
[hosting guide](deploy/README.md) for an optional Linux service.

## Development

Run the tests after installing the dataset:

```bash
uv run python -m unittest discover -s tests
```

The prediction pipeline lives in
[af3-tf-motif](https://github.com/czbiohub-sf/af3-tf-motif).

## License and policies

The app code is released under the [MIT license](LICENSE). AlphaFold 3 outputs
and derived data, including the bundled scientific illustrations, are subject to the
[AlphaFold 3 Output Terms of Use](https://github.com/google-deepmind/alphafold3/blob/main/OUTPUT_TERMS_OF_USE.md),
for non-commercial use only and not intended for clinical use.
See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the component and dataset
inventory, accompanying terms, and AlphaFold 3 citation.

See [SECURITY.md](SECURITY.md) to report a vulnerability and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for our code of conduct.
