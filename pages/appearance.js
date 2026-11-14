/** Browser-only appearance controller for Stlite / GitHub Pages.
 *
 * Streamlit's st.html() style insertion may be replaced during reruns; theme
 * styles live in app-theme.css (generated from the Python stylesheet) instead.
 * We read the selected segmented-control button, not a stale React style node.
 */
const THEMES = new Set(['light', 'dark']);

function themeFromLabel(text) {
  if (/\bClaro\b/i.test(text || '')) return 'light';
  if (/\bEscuro\b/i.test(text || '')) return 'dark';
  return null;
}

export function detectAppearance(doc) {
  const group = doc.querySelector(
    '[data-testid="stSidebar"] [data-testid="stSegmentedControl"], ' +
    '[data-testid="stSidebar"] .st-key-appearance_choice'
  );
  if (group) {
    // Versions of Streamlit use either aria-checked, aria-pressed, data-state,
    // or checked inputs for the selected choice.
    const selected = group.querySelector(
      '[aria-checked="true"], [aria-pressed="true"], [aria-selected="true"], ' +
      '[data-state="checked"], [data-testid="stBaseButton-segmented_controlActive"], input:checked'
    );
    if (selected) {
      const choice = selected.closest('button, label, [role="radio"]') || selected;
      const theme = themeFromLabel(choice.textContent || choice.getAttribute('aria-label'));
      if (theme) return theme;
    }
  }
  // Streamlit's Python app also emits a current-theme marker. This may be
  // absent from some Stlite versions; the selected UI is preferred above.
  const markers = [...doc.querySelectorAll('#eue-active-theme[data-theme]')];
  const latest = markers[markers.length - 1];
  const fallback = latest?.getAttribute('data-theme');
  return THEMES.has(fallback) ? fallback : null;
}

export function startAppearanceSync(doc, root) {
  if (!doc?.documentElement || !root) throw new Error('Página sem contêiner para sincronização do tema.');
  // Start with the actual light palette rather than a native dark flash.
  doc.documentElement.dataset.eueTheme = 'light';
  const sync = () => {
    const next = detectAppearance(doc);
    if (next && doc.documentElement.dataset.eueTheme !== next) {
      doc.documentElement.dataset.eueTheme = next;
    }
  };
  // React may update its selected state after the click. Apply the intended
  // appearance immediately while the server-side rerun completes.
  const onClick = (event) => {
    const control = event.target?.closest?.('button, label, [role="radio"]');
    const group = control?.closest?.('[data-testid="stSegmentedControl"], .st-key-appearance_choice');
    if (!group || !group.closest('[data-testid="stSidebar"]')) return;
    const next = themeFromLabel(control.textContent || control.getAttribute('aria-label'));
    if (next) doc.documentElement.dataset.eueTheme = next;
  };
  root.addEventListener('click', onClick, true);
  const observer = new MutationObserver(sync);
  observer.observe(root, {
    subtree: true, childList: true, attributes: true,
    attributeFilter: ['aria-checked', 'aria-pressed', 'aria-selected', 'data-state', 'checked', 'data-theme', 'data-testid'],
  });
  sync();
  return {
    sync,
    disconnect() { observer.disconnect(); root.removeEventListener('click', onClick, true); },
  };
}
