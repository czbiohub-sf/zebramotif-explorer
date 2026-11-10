"""Build requests for the complete Search result callback used by integration tests."""

import zebramotif.app as dashboard


def result_payload(
    dbid,
    *,
    reverse=False,
    scale="ic",
    dbd=None,
    contacts=None,
    changed="tf-dropdown.value",
    rendered_dbid=None,
):
    key = next(
        key for key in dashboard.app.callback_map if "primary-logo.figure" in key
    )
    callback = dashboard.app.callback_map[key]
    values = {
        "tf-dropdown": dbid,
        "motif-reverse-complement": reverse,
        "motif-logo-scale": scale,
        "dbd-toggle": dbd or [],
        "contacts-toggle": contacts or [],
    }
    return {
        "output": key,
        "outputs": [
            {"id": output.component_id, "property": output.component_property}
            for output in callback["output"]
        ],
        "inputs": [
            {**field, "value": values[field["id"]]} for field in callback["inputs"]
        ],
        "state": [
            {
                "id": "search-result-selection",
                "property": "data",
                "value": rendered_dbid,
            }
        ],
        "changedPropIds": [changed] if changed else [],
    }
