# Architecture

## Dependency boundaries

- `app.py`: Streamlit-only UI and forms. Reads current storage snapshot on every rerun and delegates to pure services. It does not contain arithmetic formulas or ad-hoc JSON writes.
- `models.py`: validated immutable `Device`, `Tariff`, `Scenario` and `UsageItem` objects. IDs use UUIDs rather than display names. Duplicate devices within a scenario are rejected; increase `quantity` instead.
- `bill_import.py`: pypdf-based, in-memory Copel DANF3E provider check, first-page field extraction, conservative item validation and explicit full-bill fallback. No OCR or stored PDF.
- `calculations.py`: pure functions for kWh and BRL projections. The model's active load factor applies to nominal active watts, whereas standby is computed separately in the hours not actively scheduled.
- `storage.py`: `JsonStore`, three versioned JSON files, guarded reads, same-directory temporary files + `os.replace` for atomic saves, optional appearance preference in `settings.json`, manual checkpoint with dated local backup, import validation, pre-import backup and error rollback.
- `ui_theme.py`: pure palette/CSS and Plotly-theme helpers. The in-app appearance selector saves `light` or `dark` in `settings.json`; CSS is local to the Streamlit page session, and Plotly output is restyled without mutating original figures.
- `charts.py`: Plotly figures from the calculated values; charts do not independently estimate energy.
- `presets.py`: illustrative examples, opted into by clicking a button, without changing existing devices.
- `main.py`: dependency-free CLI for estimates and diagnostics.
- `scripts/launcher.py`: standard-library cross-platform virtual environment, dependency installation and Streamlit execution.

## Data lifecycle

1. Start with an empty local data directory; the R$ 1.00/kWh default tariff is held in memory until explicitly saved.
2. Add a device: validated model, uniqueness checks, atomic `devices.json` update.
3. Create a scenario: validated model, unique scenario name and referenced IDs, atomic `scenarios.json` update.
4. Render the UI: read all JSON, verify integrity, compute `Tariff.rate`, calculate `UsageEstimate` per item, sum totals and draw Plotly charts.
5. Edit a device: scenario schedules keep the same ID and immediately use the new watts on the next rerun.
6. Auto-save: each confirmed mutation immediately updates its JSON file. The UI never auto-saves unsubmitted Streamlit form drafts.
7. Manual save: `JsonStore.save_now()` validates current data, re-writes all three JSONs, and creates a unique `data/backups/manual-*.json` checkpoint.
8. Export: one portable versioned JSON containing the three logical collections plus optional appearance setting.
9. Import a Copel PDF: read in memory, validate provider and figures, display a preview, then apply the rate only after an explicit click. This updates `settings.json` without retaining the PDF.
10. Import a JSON backup: validate entire backup and references before writing; preserve old data as an import backup; attempt rollback on partial failure.

## Concurrency and threat model

Intended for one local user. A process-wide reentrant lock protects Streamlit's concurrent threads; it **does not** coordinate independent Python processes sharing the same JSON directory. Do not run multiple server processes with the same directory or deploy this unmodified publicly. The UI does not implement user authentication, authorization, an audit log, database transactions across multiple JSON files, or remotely synchronized backups.

The file size cap (5 MiB) applies to uploaded backups; JSON import never executes code. No arbitrary filenames are accepted from imported JSON. UUID validation and strict numeric bounds prevent invalid identifiers and nonfinite electricity costs.

The PDF import is limited to 10 MiB, 1–6 pages, text-selectable content and the supported DANF3E layout. No arbitrary PDF paths are supplied to the parser; uploaded bytes are handled in memory. Extraction checks issuer name and CNPJ and refuses ambiguous values, but it is **not** cryptographic invoice authentication.

## GitHub Pages runtime

`pages/` contains the bootstrap HTML/JS/CSS for the `@stlite/browser` runtime. `scripts/build_pages.py` copies only `app.py` and the required Python package files into `dist/python`, then generates `files-manifest.json`. GitHub Actions publishes the artifact to Pages on pushes to `main`. The browser executes the original app and modules in Pyodide, not a separate JavaScript rewrite, and mounts IndexedDB at `/mnt` so `JsonStore` can persist virtual JSON files. Native Python continues using filesystem-backed `data/`.
