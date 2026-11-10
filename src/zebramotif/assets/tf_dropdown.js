(() => {
  "use strict";

  // Dash measures the options once when the menu mounts. Calculate its space
  // before that measurement, including when the previous search had one match.
  function sizeSearchMenu(event) {
    const trigger = event.target instanceof Element
      ? event.target.closest("#tf-dropdown, #home-tf-dropdown")
      : null;
    const container = trigger?.closest(".tf-search-dropdown");
    if (!container) return;

    const bounds = trigger.getBoundingClientRect();
    const viewportHeight = document.documentElement.clientHeight;
    const gap = 5;
    const edgePadding = 12;
    const availableAbove = bounds.top - gap - edgePadding;
    const availableBelow = viewportHeight - bounds.bottom - gap - edgePadding;
    container.style.setProperty(
      "--tf-search-menu-available-height",
      `${Math.max(0, availableAbove, availableBelow)}px`,
    );
  }

  document.addEventListener("pointerdown", sizeSearchMenu, true);
  document.addEventListener("keydown", sizeSearchMenu, true);
  document.addEventListener("click", sizeSearchMenu, true);
})();
