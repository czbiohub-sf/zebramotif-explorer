"""Flask endpoints, HTTP page status, and recovery for outdated browser callbacks."""

from urllib.parse import urlsplit

from flask import Response, abort, request, send_from_directory

from zebramotif import data as catalog
from zebramotif.downloads import DOWNLOADS_ENABLED, register_download_routes
from zebramotif.navigation import synchronize_tf_search
from zebramotif.utils import MEME_HEADER, meme_document, meme_record


def register_routes(app, pages):
    """Attach public downloads and request hooks to the shared Dash server."""
    server = app.server

    @server.get("/healthz")
    def health_check():
        """Report readiness after the app and its local dataset have loaded."""
        return {"status": "ok"}

    @server.get("/motifs/<motif_id>.txt")
    def motif_text(motif_id):
        """Open one primary or alternate PPM as a complete plain-text MEME document."""
        if not DOWNLOADS_ENABLED or motif_id not in catalog.MODES_BY_MOTIF_ID.index:
            abort(404)
        mode = catalog.MODES_BY_MOTIF_ID.loc[motif_id]
        text = (
            MEME_HEADER
            + "\n"
            + meme_record(mode, catalog.ALT_NAMES.get(motif_id))
            + "\n"
        )
        return Response(
            text,
            mimetype="text/plain",
            headers={"Content-Disposition": f'inline; filename="{motif_id}.txt"'},
        )

    @server.get("/motifs/tf/<dbid>.meme")
    def tf_motif_download(dbid):
        """Download the selected query's primary and all available alternate motifs."""
        modes = catalog.modes_for_query(dbid) if DOWNLOADS_ENABLED else None
        if modes is None:
            abort(404)
        return Response(
            meme_document(modes, catalog.ALT_NAMES),
            mimetype="text/plain",
            headers={
                "Content-Disposition": f'attachment; filename="zebramotif_{dbid}.meme"'
            },
        )

    @server.get("/documents/<filename>")
    def release_document(filename):
        """Serve only the public release documents linked from the website."""
        if filename not in {
            "CITATION.cff",
            "LICENSE.md",
            "release_metadata.json",
            "SCHEMA.md",
            "PROVENANCE.json",
        }:
            abort(404)
        mimetype = "application/json" if filename.endswith(".json") else "text/plain"
        return send_from_directory(catalog.DATA_DIR, filename, mimetype=mimetype)

    @server.before_request
    def page_status():
        """Return a proper status for unknown client-side pages."""
        if (
            request.method in {"GET", "HEAD"}
            and request.url_rule is not None
            and request.url_rule.rule == "/<path:path>"
            and request.path not in pages
        ):
            return Response(app.index(), status=404, mimetype="text/html")

    @server.before_request
    def refresh_outdated_callbacks():
        """Reload an open tab whose callback definitions predate an app restart."""
        if request.method != "POST" or request.path != "/_dash-update-component":
            return
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("output"), str):
            return
        fields = {}
        for kind in ("inputs", "state"):
            fields[kind] = payload.get(kind, [])
            if not isinstance(fields[kind], list) or any(
                not isinstance(field, dict) for field in fields[kind]
            ):
                return
        callback = app.callback_map.get(payload["output"])
        if callback is not None and all(
            [(field.get("id"), field.get("property")) for field in fields[kind]]
            == [(field["id"], field["property"]) for field in callback[kind]]
            for kind in fields
        ):
            return

        location = urlsplit(request.referrer or "")
        pathname = location.path
        if pathname not in pages:
            pathname = "/search"
        search = f"?{location.query}" if location.query else ""
        if pathname == "/search":
            values = {
                (field.get("id"), field.get("property")): field.get("value")
                for field in fields["inputs"]
                if isinstance(field.get("id"), str)
            }
            selected = values.get(("tf-dropdown", "value"))
            search = values.get(
                ("search-url", "search"), values.get(("url", "search"), search)
            )
            navigation = synchronize_tf_search(
                selected,
                search,
                catalog.TF2REP_BY_DBID.index,
                from_url=any(
                    changed in {"url.search", "search-url.search"}
                    for changed in payload.get("changedPropIds", [])
                )
                or ("tf-dropdown", "value") not in values
                or not payload.get("changedPropIds"),
            )
            search = navigation.search
        server.logger.info(
            "Refreshing outdated browser callback: %s", payload["output"]
        )
        # A relative href differs from Location's absolute href, so refresh=True forces
        # a document reload even when the selected URL itself has not changed.
        return {
            "multi": True,
            "response": {},
            "sideUpdate": {"url": {"refresh": True, "href": pathname + search}},
        }

    if DOWNLOADS_ENABLED:
        register_download_routes(server, catalog.DOWNLOADS)
