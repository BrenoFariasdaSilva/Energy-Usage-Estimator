import assert from 'node:assert/strict';
import test from 'node:test';
import { fileDescriptors, REQUIREMENTS, stliteOptions, STLite_CDN } from '../pages/boot.js';

const manifest = [
  'app.py',
  'src/energy_estimator/__init__.py',
  'src/energy_estimator/bill_import.py',
];

test('pages config loads the original Python app with a persistent IDBFS mount', () => {
  const options = stliteOptions(manifest, new URL('https://example.github.io/eue/python/'));
  assert.equal(options.entrypoint, 'app.py');
  assert.deepEqual(options.idbfsMountpoints, ['/mnt']);
  assert.deepEqual(options.requirements, [...REQUIREMENTS]);
  assert.equal(options.files['app.py'].url, 'https://example.github.io/eue/python/app.py');
  assert.equal(options.files['src/energy_estimator/bill_import.py'].url,
    'https://example.github.io/eue/python/src/energy_estimator/bill_import.py');
  assert.equal(options.streamlitConfig['browser.gatherUsageStats'], false);
  assert.equal(options.streamlitConfig['server.maxUploadSize'], 10);
  assert.equal(options.streamlitConfig['theme.base'], 'dark');
  assert.equal(options.streamlitConfig['theme.backgroundColor'], '#0B121C');
  assert.equal(options.streamlitConfig['theme.textColor'], '#F1F7FF');
  assert.match(STLite_CDN, /@stlite\/browser@1\.11\.0\/build\/stlite\.js/);
});

test('paths are relative, safe for user/repository Pages subdirectories', () => {
  for (const root of ['https://example.com/', 'https://user.github.io/My-Repo/']) {
    const base = new URL('python/', root);
    const files = fileDescriptors(manifest, base);
    for (const [path, item] of Object.entries(files)) {
      assert.equal(item.url, new URL(path, base).href);
    }
  }
});

test('rejects missing entrypoint and injected/duplicate paths', () => {
  assert.throws(() => fileDescriptors([]), /app\.py/);
  assert.throws(() => fileDescriptors(['app.py', '../data/settings.json']), /inesperado/);
  assert.throws(() => fileDescriptors(['app.py', 'app.py']), /repetidos/);
  assert.throws(() => fileDescriptors(['app.py', 'src/energy_estimator/sub/secret.py']), /inesperado/);
});

// The Pages controller must not trust a stale Python marker over the sidebar.
import { detectAppearance } from '../pages/appearance.js';

test('selected sidebar appearance wins over a stale browser marker', () => {
  const selected = { closest: () => ({ textContent: '◐ Escuro' }) };
  const group = { querySelector: () => selected };
  const staleLightMarker = { getAttribute: () => 'light' };
  const doc = {
    querySelector: () => group,
    querySelectorAll: () => [staleLightMarker],
  };
  assert.equal(detectAppearance(doc), 'dark');
  assert.equal(detectAppearance({
    querySelector: () => null,
    querySelectorAll: () => [{ getAttribute: () => 'light' }],
  }), 'light');
});
