# GitHub Pages (browser edition)

GitHub Pages serves **static files only**; it cannot run `streamlit run app.py` on a server. This repository instead uses [Stlite](https://stlite.net/browser/), which executes Streamlit and the existing Python calculation/PDF code **inside each visitor's browser** through Pyodide/WebAssembly.

The regular Windows/macOS/Linux launcher is unaffected; Pages is an additional distribution option.

## Publish the website

1. Add the contents of this project to a GitHub repository, ideally named `Energy-Usage-Estimator`, and use `main` as its default branch.
2. On GitHub open **Settings → Pages → Build and deployment → Source** and choose **GitHub Actions**. This is essential: do not choose *Deploy from a branch* for this workflow.
3. Push to `main`, or open **Actions → Deploy GitHub Pages → Run workflow**. Workflow `.github/workflows/pages.yml` checks the generated static bundle and deploys it.
4. Read the Pages URL in the deployment job. For a repository named `Energy-Usage-Estimator` under account `USERNAME`, the normal address is `https://USERNAME.github.io/Energy-Usage-Estimator/`.
5. For subsequent changes, pushing to `main` redeploys the application. Pull requests run build checks but do **not** deploy.

You do **not** need to commit `dist/` or create a `gh-pages` branch. Deployment uses the Actions Pages artifact.

## Local preview of the generated site

From the repository root:

```bash
python scripts/build_pages.py
python -m http.server 8000 --directory dist
```

Open `http://localhost:8000/`. The application needs internet access during initial loading to fetch the Stlite runtime, Pyodide and supported Python packages. Do not open `dist/index.html` as a `file://` URL; browsers restrict module and asset loading in that mode.

To run the original Python server instead, use `python scripts/launcher.py run` (or the OS-specific start script).

## Supported features

The website bundles the original `app.py` and all nine Python modules; it does not reimplement tariff calculations in JavaScript. The browser runtime receives the same forms, calculations, Plotly charts, scenario data model, Copel PDF parser and JSON backup code.

- **No application server:** Streamlit/Python runs in your browser. GitHub Pages only supplies public static source files.
- **Browser-specific JSON persistence:** `/mnt` is backed by IndexedDB using Stlite's `idbfsMountpoints`. Data is private to the browser profile and site origin, not a file in the checked-out Git repository. The app chooses `/mnt/energy-usage-estimator` when running under Pyodide; native Python still uses `data/` or `ENERGY_ESTIMATOR_DATA_DIR`.
- **Backup/export:** `Dados e backups → Baixar backup completo (JSON)` downloads portable JSON. Import that backup in the browser edition or native edition. Manual checkpoints are also stored in IndexedDB until browser data is cleared.
- **Copel PDF:** The supported PDF is parsed in browser memory by `pypdf`. The application does not upload the file to Copel or to a Python server. PDFs, downloaded backups and private data are never included in the published artifact.
- **Light/dark mode:** The Pages build derives `app-theme.css` automatically from the existing Python `ui_theme.py` stylesheet. The host-page controller (`appearance.js`) follows the selected sidebar option, while Stlite starts from the explicit native light palette. The preference remains saved in browser-local JSON. The native desktop Streamlit stylesheet is unchanged.

## Limits and safety

- The site may load slowly the first time and may consume considerable RAM. WebAssembly/Pyodide and Plotly are significantly heavier than a typical static page.
- The browser runtime **requires JavaScript and downloads from the Stlite/Pyodide package CDNs**. These services receive normal network metadata (such as the visitor's IP), but the application's own code does not intentionally send bills, appliances, saved scenarios or personal JSON backups to them.
- Browser private/incognito storage or cleared site data can remove saved devices and scenarios. **Export JSON backups regularly.** The service does not implement cloud sync between devices or browsers.
- The website is publicly reachable. Do not add private invoices, exported backups, `data/`, `.env`, or API secrets to Git. The build uses an explicit allowlist, not a copy of the repository directory.
- Dependency installation in Pyodide and native Streamlit may differ. The build checks syntax, manifests and serverless wiring, but it cannot guarantee each browser's compatibility. Validate the live Pages URL after deployment, especially PDF import, IndexedDB persistence, Plotly charts and both themes.

## Build contents

`python scripts/build_pages.py` creates `dist/` with `index.html`, `pages.css`, `appearance.js`, the generated `app-theme.css`, the static launcher, a copy of the license, a file manifest and the minimal Python sources loaded as URLs. The builder never includes `data/`, `.env`, screenshots, backups, tests or sample invoices. It blocks accidental deletion of unrelated output directories.

The runtime version is pinned in `pages/index.html` and `pages/boot.js` (`@stlite/browser@1.11.0`). Upgrade both together with regression tests; do not use floating `latest` in production.

## Theme regression checks

The static browser bundle **does not** inject a second stylesheet through `st.html()` when running under Stlite. Instead, the build generates CSS from `ui_theme.py` and the host controller detects the appearance selected in the Streamlit sidebar (`Claro`/`Escuro`). This is necessary because Stlite does not automatically read the repository's local `.streamlit/config.toml`.

After building, verify the generated CSS and UI behavior with a locally installed Chromium and Playwright:

```bash
python scripts/build_pages.py
python scripts/verify_pages_appearance.py
```

This exercises the generated CSS and the actual browser JS in **simulated Streamlit markup**, testing `Claro → Escuro → Claro`, file-upload text/icon, number-input contrast, and all six navigation options. It is **not a full Stlite WebAssembly browser end-to-end test**. For final deployment, also test the live site with both themes, an actual Copel invoice, and JSON persistence across page reloads.
