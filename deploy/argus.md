# Argus deployment

The public website runs on Argus as `zebramotif-explorer` (`prod` on `prod-biohub`).

## Setup

```bash
argus register app        # repo czbiohub-sf/zebramotif-explorer, root .
argus register env --app zebramotif-explorer   # prod on prod-biohub
read -rs "ZURL?Zenodo share URL: " && echo && argus set secret --app zebramotif-explorer --env prod ZEBRAMOTIF_ZENODO_URL "$ZURL"; unset ZURL
```

The secret is only needed while the Zenodo record is restricted.

## Deploy

Pushes to `main` that change the image build and deploy prod. To build manually,
run the **Argus Docker Build** workflow on `main` with `app=zebramotif-explorer`.

```bash
argus list stacks --app zebramotif-explorer --env prod
```

To roll back, restore a previous image tag in `.infra/prod/values.yaml`.

Downloads are enabled by default. To disable them in prod, set
`ZEBRAMOTIF_DOWNLOADS` to `"off"` under `stack.services.app.env` in
`.infra/prod/values.yaml`. Remove the entry to enable downloads again.

The dataset is cached on a 2 GiB volume at `/var/lib/zebramotif/datasets`, so
only the first start downloads it.
