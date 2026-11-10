(() => {
  "use strict";

  // Methods mounts after the browser's initial fragment lookup. Restore a
  // shared section link once Dash has rendered it; normal in-page links stay native.
  const sections = new Set([
    "methods-predictions",
    "methods-logos",
    "methods-scores",
    "methods-dataset",
    "methods-cite",
    "methods-terms",
  ]);
  const hash = window.location.hash;
  const id = hash.slice(1);
  if (window.location.pathname !== "/methods" || !sections.has(id)) return;

  function stillRequested() {
    return window.location.pathname === "/methods" && window.location.hash === hash;
  }

  const observer = new MutationObserver(restoreSection);

  function restoreSection() {
    if (!stillRequested()) {
      observer.disconnect();
      return;
    }
    const section = document.getElementById(id);
    if (!section?.closest(".methods-page")) return;
    observer.disconnect();

    // Resolve layout and font loading before measuring the final section position.
    section.getBoundingClientRect();
    const ready = document.fonts?.ready || Promise.resolve();
    ready.then(() => requestAnimationFrame(() => {
      if (stillRequested() && section.isConnected) {
        section.scrollIntoView({ block: "start", behavior: "instant" });
      }
    }));
  }

  observer.observe(document.documentElement, { childList: true, subtree: true });
  restoreSection();
  window.addEventListener("pagehide", () => observer.disconnect(), { once: true });
})();
