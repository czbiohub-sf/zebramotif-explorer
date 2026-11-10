(() => {
  "use strict";

  let expanded = null;
  let previousFocus = null;
  let previousScroll = null;
  let backdrop = null;
  const focusable = "button, a[href], input, select, textarea, [tabindex]";

  let framingTimer = null;
  let framingViewer = null;
  let framingSubscription = null;
  let cameraSubscription = null;
  const framedStructures = new WeakMap();

  function scheduleFraming() {
    if (framingTimer === null) framingTimer = setTimeout(frameStructure, 100);
  }

  function viewerInstance() {
    let node = document.querySelector("#structure-content canvas");
    while (node) {
      const key = Object.keys(node).find(name => (
        name.startsWith("__reactFiber$") || name.startsWith("__reactInternalInstance$")
      ));
      for (let fiber = key ? node[key] : null; fiber; fiber = fiber.return) {
        if (fiber.stateNode?.viewer?._plugin) return fiber.stateNode;
      }
      node = node.parentElement;
    }
    return null;
  }

  function frameStructure() {
    framingTimer = null;
    const viewer = viewerInstance();
    if (viewer !== framingViewer) {
      framingSubscription?.unsubscribe();
      cameraSubscription?.unsubscribe();
      cameraSubscription = null;
      framingViewer = viewer;
      framingSubscription = viewer?.viewer._plugin.behaviors.state.isBusy.subscribe(busy => {
        if (!busy) scheduleFraming();
      });
    }
    if (!viewer) {
      if (document.querySelector("#structure-content canvas")) scheduleFraming();
      return;
    }
    const plugin = viewer.viewer._plugin;
    if (plugin.disposed) return;
    if (!plugin.canvas3d) {
      scheduleFraming();
      return;
    }
    if (!cameraSubscription) {
      const camera = plugin.canvas3d.camera;
      cameraSubscription = camera.stateChanged.subscribe(state => {
        // Resets, presets, and restored snapshots must never re-enable depth effects.
        if ((state.fog !== undefined && state.fog !== 0) || state.clipFar === true) {
          const transition = camera.transition;
          camera.setState({
            ...(transition.inTransition ? transition.target : camera.state),
            fog: 0,
            clipFar: false,
          }, transition.inTransition ? transition.durationMs : 0);
        }
      });
    }
    const data = viewer.props.data;
    if (!viewer.props.focus?.targets?.length) return;
    const structure = plugin.managers.structure.hierarchy.current.structures[0];
    const previous = framedStructures.get(viewer);
    if (previous && previous.structure === structure && previous.data === data) return;

    // dash-molstar applies its initial focus before its asynchronous model load finishes.
    // Wait for all custom components, then apply it once for this loaded structure.
    const expected = data?.component;
    const components = structure?.components;
    if (plugin.behaviors.state.isBusy.value || !components?.length || !expected?.length
        || previous?.structure === structure || components.length !== expected.length
        || expected.some(item => !components.some(component => (
          component.cell.obj?.label === item.label
          && component.representations.length === item.representation.length
        )))) {
      scheduleFraming();
      return;
    }
    viewer.handleFocusChange(viewer.props.focus);
    framedStructures.set(viewer, { structure, data });
  }

  new MutationObserver(scheduleFraming).observe(document.body, {
    childList: true,
    subtree: true,
  });
  scheduleFraming();

  function resizeViewer() {
    // Mol* keeps the same canvas and camera while its surrounding panel changes size.
    requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
  }

  function updateButton(panel, isExpanded) {
    const button = panel.querySelector("#expand-structure-viewer");
    if (!button) return;
    button.textContent = isExpanded ? "Close expanded view" : "Expand viewer";
    button.setAttribute("aria-expanded", String(isExpanded));
  }

  function collapse() {
    if (!expanded) return;
    const restoreScroll = expanded.isConnected && expanded.style.display !== "none";
    observer.disconnect();
    expanded.classList.remove("is-expanded");
    expanded.removeAttribute("role");
    expanded.removeAttribute("aria-modal");
    updateButton(expanded, false);
    document.body.classList.remove("structure-viewer-open");
    backdrop?.remove();
    backdrop = null;
    expanded = null;
    if (restoreScroll && previousScroll) {
      window.scrollTo({
        left: previousScroll.x,
        top: previousScroll.y,
        behavior: "instant",
      });
    }
    previousScroll = null;
    if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true });
    previousFocus = null;
    resizeViewer();
  }

  // Release the overlay if a search is cleared or navigation removes the result.
  const observer = new MutationObserver(() => {
    if (expanded && (!expanded.isConnected || expanded.style.display === "none")) {
      collapse();
    }
  });

  function expand(panel) {
    previousFocus = document.activeElement;
    previousScroll = { x: window.scrollX, y: window.scrollY };
    expanded = panel;
    backdrop = document.createElement("div");
    backdrop.className = "structure-viewer-backdrop";
    backdrop.setAttribute("aria-hidden", "true");
    backdrop.addEventListener("click", collapse);
    document.body.appendChild(backdrop);
    document.body.classList.add("structure-viewer-open");
    panel.classList.add("is-expanded");
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    updateButton(panel, true);
    observer.observe(panel, { attributes: true, attributeFilter: ["style"] });
    const page = document.getElementById("page-content");
    if (page) observer.observe(page, { childList: true });
    resizeViewer();
  }

  document.addEventListener("click", event => {
    const button = event.target instanceof Element
      ? event.target.closest("#expand-structure-viewer")
      : null;
    if (!button) return;
    event.preventDefault();
    const panel = button.closest("#structure-section");
    if (expanded) collapse();
    else if (panel) expand(panel);
  });

  document.addEventListener("keydown", event => {
    if (!expanded) return;
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      collapse();
    } else if (event.key === "Tab") {
      const elements = [...expanded.querySelectorAll(focusable)].filter(element => (
        !element.disabled && element.tabIndex >= 0 && element.getClientRects().length
      ));
      const first = elements[0];
      const last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
  }, true);
})();
