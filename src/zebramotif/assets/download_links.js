(() => {
  "use strict";

  const initialized = new WeakSet();
  let scheduled = false;
  const number = new Intl.NumberFormat("en", { maximumFractionDigits: 1 });

  function fileSize(bytes) {
    if (bytes >= 1e6) return `${number.format(bytes / 1e6)} MB`;
    if (bytes >= 1e3) return `${number.format(bytes / 1e3)} kB`;
    return `${bytes} B`;
  }

  function initialize() {
    scheduled = false;
    for (const option of document.querySelectorAll(".download-option[data-download-path]")) {
      if (initialized.has(option)) continue;
      initialized.add(option);
      const url = new URL(option.dataset.downloadPath, window.location.origin);
      const size = option.querySelector(".download-file-size");
      // The saved-file size remains correct when HTTP transfer compression is enabled.
      fetch(url.href, { method: "HEAD" }).then(response => {
        const length = response.headers.get("X-File-Size");
        const bytes = length === null ? NaN : Number(length);
        if (!response.ok || !Number.isSafeInteger(bytes) || bytes < 0) {
          throw new Error("Size unavailable");
        }
        if (!option.isConnected) return;
        size.textContent = fileSize(bytes);
        size.title = `${bytes.toLocaleString("en")} bytes`;
        size.dataset.bytes = String(bytes);
      }).catch(() => {
        if (option.isConnected) size.textContent = "Size unavailable";
      });
    }
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(initialize);
  }

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
      previousFocus?.focus({ preventScroll: true });
    }
  }

  document.addEventListener("click", async event => {
    const button = event.target instanceof Element
      ? event.target.closest(".download-url-copy")
      : null;
    if (!button) return;
    const option = button.closest(".download-option");
    const status = option.querySelector(".download-copy-status");
    const url = new URL(option.dataset.downloadPath, window.location.origin).href;
    status.textContent = "";
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
        if (option.isConnected) status.textContent = "Link copied.";
        return;
      }
    } catch (_) {
      // Plain HTTP and denied clipboard access can use a temporary text selection.
    }
    if (!option.isConnected) return;
    try {
      if (copyWithSelection(url)) {
        status.textContent = "Link copied.";
        return;
      }
    } catch (_) {
      // Report failure when the browser blocks both clipboard APIs.
    }
    status.textContent = "Couldn’t copy the link. Please try again.";
  });

  new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
  schedule();
})();
