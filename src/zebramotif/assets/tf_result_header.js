/* Share the selected query using the browser's current origin. */
(function () {
  let copyRequest = 0;

  function copyWithSelection(text) {
    const previousFocus = document.activeElement;
    const input = document.createElement("textarea");
    input.value = text;
    input.readOnly = true;
    input.style.position = "fixed";
    input.style.left = "-10000px";
    document.body.appendChild(input);
    try {
      input.select();
      return document.execCommand("copy");
    } finally {
      input.remove();
      if (previousFocus) previousFocus.focus({ preventScroll: true });
    }
  }

  window.dash_clientside = Object.assign({}, window.dash_clientside, {
    tfResultHeader: {
      copyLink: async function (clicks, dbid) {
        const request = ++copyRequest;
        function result(message, style, value) {
          return request === copyRequest
            ? [message, style, value]
            : Array(3).fill(window.dash_clientside.no_update);
        }
        const trigger = window.dash_clientside.callback_context.triggered_id;
        if (trigger !== "copy-tf-link" || !clicks || !dbid) {
          return result("", { display: "none" }, "");
        }
        const url = new URL("/search", window.location.href);
        url.searchParams.set("tf", dbid);
        const text = url.href;
        try {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
            return result("Link copied.", { display: "none" }, "");
          }
        } catch (_) {
          // Plain HTTP and denied clipboard permissions can use a text selection.
        }
        try {
          if (copyWithSelection(text)) {
            return result("Link copied.", { display: "none" }, "");
          }
        } catch (_) {
          // Keep a manual copy option when the browser blocks both clipboard APIs.
        }
        return result("Select and copy the link below.", {}, text);
      },
    },
  });
})();
