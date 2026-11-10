# Third party notices

ZebraMotif software is covered by the [MIT license](LICENSE). The scientific
illustrations and linked dataset include AlphaFold 3 outputs and derivatives
with separate terms. Reference annotations and installed libraries retain their
providers' licenses.

## Bundled scientific illustrations

The following files in `src/zebramotif/assets/` contain rendered or adapted
predictions from the ZebraMotif dataset, produced by the
[af3-tf-motif pipeline](https://github.com/czbiohub-sf/af3-tf-motif):

| Files | Content and modifications |
| --- | --- |
| `home-irf2-structure.png` | Rendered protein–DNA structure for the irf2 example. |
| `home-irf2-logo.svg`, `home-irf2-logo-narrow.svg` | Predicted irf2 motif rendered as sequence logos in two layouts. |
| `methods-structures.svg`, `methods-preferences.svg`, `methods-clusters.svg`, `methods-modes.svg` | Cropped or arranged workflow illustrations adapted from the project's Fig4 panel A, as recorded in their descriptions. |

These illustrations are provided under and subject to the
[AlphaFold 3 Output Terms of Use](notices/AF3_OUTPUT_TERMS_OF_USE.md), including
their non-commercial-use restrictions, attribution, and notice requirements.
The required [Legally Binding Terms of Use](notices/Legally%20Binding%20Terms%20of%20Use.txt)
notice accompanies them. Preserve these documents when redistributing the
illustrations. [Notice provenance](notices/sources.json) records the source and
checksum of the upstream terms.

AlphaFold 3 citation: Abramson, J. et al. Accurate structure prediction of
biomolecular interactions with AlphaFold 3. *Nature* **630**, 493–500 (2024).
[doi:10.1038/s41586-024-07487-w](https://doi.org/10.1038/s41586-024-07487-w).

## Python dependencies

The application installs these libraries as dependencies. It does not vendor
their source trees. Versions below correspond to the reviewed `uv.lock`;
that lockfile also lists transitive dependencies. Preserve each distribution's
own license files when distributing an environment or container.

| Component | Locked version | License and source |
| --- | --- | --- |
| Dash | 4.2.0 | [MIT](https://github.com/plotly/dash/blob/dev/LICENSE) |
| dash-bootstrap-components | 2.0.4 | [Apache-2.0](https://github.com/dbc-team/dash-bootstrap-components/blob/main/LICENSE) |
| dash-molstar | 1.3.2 | [LGPL-2.1](https://github.com/everburstSun/dash-molstar/blob/main/LICENSE); installed as an unmodified dependency. Preserve its license and source notices when redistributing it. |
| Gunicorn | 26.0.0 | [MIT](https://github.com/benoitc/gunicorn/blob/master/LICENSE) |
| Matplotlib | 3.11.0 | [Matplotlib license, based on the PSF license](https://matplotlib.org/stable/project/license.html), plus bundled third-party notices. |
| NumPy | 2.4.6 | [BSD-3-Clause and bundled licenses](https://github.com/numpy/numpy/blob/main/LICENSE.txt). Installed metadata also lists 0BSD, MIT, Zlib, and CC0-1.0. |
| pandas | 3.0.3 | [BSD-3-Clause](https://github.com/pandas-dev/pandas/blob/main/LICENSE) |
| Plotly | 6.8.0 | [MIT](https://github.com/plotly/plotly.py/blob/main/LICENSE.txt) |
| PyArrow | 24.0.0 | [Apache-2.0](https://github.com/apache/arrow/blob/main/LICENSE.txt), plus the distribution's notices. |

The Mol* viewer included by dash-molstar has its own
[MIT license](https://github.com/molstar/molstar/blob/master/LICENSE).
That does not replace the dash-molstar wrapper's LGPL-2.1 license.

## External styles and fonts

The browser requests these resources from external providers; font binaries
and the Bootstrap stylesheet are not copied into this repository.

| Resource | Source and license |
| --- | --- |
| Bootstrap CSS | Theme selected through dash-bootstrap-components; [MIT](https://github.com/twbs/bootstrap/blob/main/LICENSE). |
| Hanken Grotesk | Google Fonts; [SIL Open Font License 1.1](https://github.com/google/fonts/blob/main/ofl/hankengrotesk/OFL.txt). |
| STIX Two Text | Google Fonts; [SIL Open Font License 1.1](https://github.com/google/fonts/blob/main/ofl/stixtwotext/OFL.txt). |

## Linked dataset and reference annotations

Dataset `0.1` is a restricted Zenodo record pending release review. The dataset
installer identifies record `23380219` and DOI `10.5281/zenodo.23380219`.
The download contains its own `LICENSE.md`, `CITATION.cff`, `PROVENANCE.json`,
and `notices/`. Its structures, predicted motifs, confidence summaries, contacts,
and AF3-derived domain-placement flags follow the AlphaFold 3 Output Terms.
The repository's MIT license does not grant additional rights to these data.

| Resource | Included contribution | License and attribution |
| --- | --- | --- |
| [AlphaFold 3](https://github.com/google-deepmind/alphafold3) | Predicted structures and derived scientific data and illustrations. | [Custom Output Terms](notices/AF3_OUTPUT_TERMS_OF_USE.md), including non-commercial-use restrictions, attribution, and notice requirements. |
| [AnimalTFDB 4.0](https://guolab.wchscu.cn/AnimalTFDB4/) | Zebrafish TF catalog and family labels. | Attribution: Shen et al., *Nucleic Acids Research* (2023). These reference annotations retain their provider's terms; the software's MIT license does not apply to them. |
| [JASPAR](https://jaspar.elixir.no/about/) | Motif identifiers and comparison inputs from the 2024 CORE vertebrate collection. | CC BY 4.0; attribution: Rauluseviciute et al., *Nucleic Acids Research* (2024). |
| [InterPro](https://interpro-documentation.readthedocs.io/en/latest/license.html) and [Pfam](https://www.ebi.ac.uk/interpro/entry/pfam/) | Domain accessions, descriptions, and coordinates produced through InterProScan 5.73-104.0, including Pfam 37.2. | Downloadable InterPro and Pfam data are CC0 1.0. Member-database signature collections can have separate terms, including PROSITE below. |
| [PROSITE](https://prosite.expasy.org/prosite_license.html) | The export contains 11 domain rows with `PS` accessions; metadata reports PROSITE Profiles 2023_05. | Copyright SIB Swiss Institute of Bioinformatics; [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/), including non-commercial and no-derivatives restrictions. Retain attribution and this license information for the 11 rows. |
| [ZFIN](https://zfin.atlassian.net/wiki/spaces/general/pages/1942160112) | Frozen Ensembl-to-ZFIN mapping and gene identifiers. | CC BY 4.0 for data and annotations; retain attribution. The original snapshot date is unrecorded. |
| [Ensembl](https://www.ensembl.org/info/about/legal/disclaimer.html) | Gene identifiers and source sequence references. | Ensembl-generated data are available without restriction, subject to third-party constraints. The sequence assembly and annotation release are unrecorded. |

The upstream pipeline uses AlphaFold 3 model parameters and an
[NA-MPNN](https://github.com/baker-laboratory/NA-MPNN) checkpoint. Neither their
source code nor model weights are included in this repository or the installed
website dataset. Obtain them separately under their upstream terms when running
that pipeline.
