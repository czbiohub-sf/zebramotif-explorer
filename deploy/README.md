# Deployment

For dataset installation and access, see [Run locally](../README.md#run-locally).

For the public website, see the [Argus deployment guide](argus.md).

## Linux service

The optional [systemd service example](zebramotif.service.example) runs Gunicorn
on a Linux host. It starts at boot and restarts after an unexpected exit, using
2 workers, 4 threads per worker, and a 120-second timeout. Logs go to the system
journal. The service reads the application and installed dataset, with a separate
writable Matplotlib cache managed by systemd.

The example listens on `127.0.0.1:8568`. Configure HTTPS and traffic routing through
the hosting platform. Nothing has been installed, enabled, or published by these
example files.

### Target values to supply

| Value | Supply on the Linux host |
|---|---|
| Host | A persistent Linux host with systemd and administrator access. |
| `@APP_ROOT@` | Absolute path to the ZebraMotif checkout containing `.venv/`. |
| `@DATA_ROOT@` | Absolute path to the installed dataset, readable by the service account. Install it separately from the checkout. |
| `@APP_USER@`, `@APP_GROUP@` | Existing unprivileged service account and group with read access to the checkout and execute access to its parent directories and Python environment. |
| Persistent storage | Retain the installed dataset across deployments. The service account needs read access to it. |

### Prepare and validate on that host

Run from the chosen checkout. Recreate the Python environment from the existing lockfile
on a new host rather than copying a virtual environment between machines. For
restricted data, set `ZEBRAMOTIF_ZENODO_URL_FILE` to a private file containing
an authorized Zenodo share/preview URL, as described in [Run locally](../README.md#run-locally):

```bash
uv sync --frozen
.venv/bin/python -m zebramotif.dataset --data-dir /path/to/zebramotif-data/0.1
cp deploy/zebramotif.service.example /tmp/zebramotif.service
```

Edit the service copy, replacing every `@...@` value with the target values above.
Then validate without starting the server:

```bash
ZEBRAMOTIF_DATA_DIR=/path/to/zebramotif-data/0.1 .venv/bin/python -m gunicorn --check-config zebramotif.app:server
systemd-analyze verify /tmp/zebramotif.service
```

### Install and start on that host

```bash
sudo install -m 0644 /tmp/zebramotif.service /etc/systemd/system/zebramotif.service
sudo systemctl daemon-reload
sudo systemctl enable --now zebramotif.service
```

### Verify and operate

Check the app directly and inspect the service logs:

```bash
curl --fail --silent --show-error http://127.0.0.1:8568/_dash-layout >/dev/null
sudo systemctl status zebramotif.service
sudo journalctl -u zebramotif.service -n 100 --no-pager
```

Through the hosting platform's URL, check a TF search, its structure, and both MEME
and ZIP downloads. On the selected host, verify that the service returns after a
reboot and that the app recovers from an unexpected process exit.

After updating code or selecting a new installed data release, restart the app
to load the new tables:

```bash
sudo systemctl restart zebramotif.service
```

Retain the previous checkout, Python environment, and matching data release for rollback.
A manual `systemctl stop zebramotif.service` keeps the app stopped despite its restart
policy. See [systemd restart semantics](https://github.com/systemd/systemd/blob/main/man/systemd.service.xml)
and [Gunicorn's deployment guidance](https://gunicorn.org/deploy/) for these process
settings.
