import { startAppearanceSync } from './appearance.js';

// Static Pages entry point. No app data or PDF is uploaded to a server.
// Versions and URLs are intentionally fixed; upgrade only with an explicit test.
export const STLite_VERSION = '1.11.0';
export const STLite_CDN = `https://cdn.jsdelivr.net/npm/@stlite/browser@${STLite_VERSION}/build/stlite.js`;
export const REQUIREMENTS = Object.freeze([
  'pandas>=2.2,<3',
  'plotly>=6,<7',
  'pypdf>=5.9,<7',
]);

export function fileDescriptors(names, base = new URL('./python/', import.meta.url)) {
  if (!Array.isArray(names) || !names.includes('app.py')) {
    throw new Error('Manifesto inválido: app.py ausente.');
  }
  const files = {};
  for (const name of names) {
    if (typeof name !== 'string' || !/^(app\.py|src\/energy_estimator\/[A-Za-z_][A-Za-z_0-9]*\.py)$/.test(name)) {
      throw new Error('Manifesto contém um caminho inesperado.');
    }
    if (Object.prototype.hasOwnProperty.call(files, name)) {
      throw new Error('Manifesto contém arquivos repetidos.');
    }
    files[name] = { url: new URL(name, base).href };
  }
  return files;
}

export function stliteOptions(names, base) {
  return {
    entrypoint: 'app.py',
    files: fileDescriptors(names, base),
    requirements: [...REQUIREMENTS],
    // stlite uses IndexedDB persistence for this directory, not transient MEMFS.
    idbfsMountpoints: ['/mnt'],
    streamlitConfig: {
      'browser.gatherUsageStats': false,
      'client.toolbarMode': 'viewer',
      'server.maxUploadSize': 10,
      // Stlite is not launched through the repository's .streamlit/config.toml.
      // Start from the app's dark default rather than the browser/OS preference.
      'theme.base': 'dark',
      'theme.primaryColor': '#32A9EF',
      'theme.backgroundColor': '#0B121C',
      'theme.secondaryBackgroundColor': '#142333',
      'theme.textColor': '#F1F7FF',
    },
  };
}

export async function boot({
  loadRuntime = () => import(STLite_CDN),
  loadManifest = () => fetch(new URL('./files-manifest.json', import.meta.url)),
  root = document.getElementById('root'),
  splash = document.getElementById('splash'),
  status = document.getElementById('launch-status'),
} = {}) {
  try {
    if (!root) throw new Error('O contêiner da aplicação está ausente.');
    const response = await loadManifest();
    if (!response.ok) throw new Error(`Não foi possível carregar os arquivos da aplicação (HTTP ${response.status}).`);
    const files = await response.json();
    // Install the host-side theme controller before Streamlit begins rendering.
    // It follows the selected sidebar option, never the OS/browser dark mode.
    startAppearanceSync(root.ownerDocument, root);
    const { mount } = await loadRuntime();
    if (typeof mount !== 'function') throw new Error('O runtime Stlite não disponibilizou mount().');
    status && (status.textContent = 'Inicializando o painel e instalando as dependências Python, se necessário...');
    const controller = await mount(stliteOptions(files), root);

    // The runtime may return before Python finishes initializing. Keep the
    // splash until the real app renders (not merely until JS is downloaded).
    if (splash) {
      const ready = () => root.querySelector('[data-testid="stApp"]');
      const showApp = () => {
        splash.classList.add('ready');
        splash.setAttribute('aria-hidden', 'true');
        observer.disconnect();
        window.setTimeout(() => splash.remove(), 300);
      };
      const observer = new MutationObserver(() => { if (ready()) showApp(); });
      observer.observe(root, { childList: true, subtree: true });
      if (ready()) showApp();
    }
    return controller;
  } catch (error) {
    if (splash) splash.classList.add('failed');
    if (splash) splash.classList.remove('ready');
    const heading = splash?.querySelector('h1');
    if (heading) heading.textContent = 'Não foi possível iniciar o aplicativo';
    if (status) status.textContent = `${String(error.message || error)} Verifique sua conexão, recarregue a página ou utilize a versão local.`;
    throw error;
  }
}

// Test modules can import these pure helpers without mounting an app.
if (typeof document !== 'undefined' && document.getElementById('root')) {
  boot().catch((error) => console.error('Energy Usage Estimator startup:', error));
}
