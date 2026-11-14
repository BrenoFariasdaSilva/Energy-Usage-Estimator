# Privacy and data retention

The program stores device and billing information as local JSON in the application directory's `data/` folder by default. That folder is excluded from Git, as are `.env` files, Python bytecode and virtualenv dependencies.

There is **no application account**, analytics server, cloud sync or utility account integration. The application does not send user-entered appliance or bill data to an external API. Streamlit's built-in usage statistics are disabled by configuration. Dependency installation at first startup does communicate with Python package registries, and external packages or the browser may have their own network behavior.

**Important:** "local" means local to the machine running `streamlit run app.py`. If you deploy the server to a network, all visitors could access the same JSON dataset. Streamlit session state is per browser session, but the JSON store is shared among server sessions. Therefore, treat this as a single-user application and bind it to localhost as the included launcher does.

A complete JSON export (including the light/dark theme preference) allows you to move the data to another machine. Manual checkpoints remain in `data/backups/` and are not sent to the browser unless explicitly downloaded. The import process takes an automatic previous-state backup. Do not publish exported backup files or commit the ignored `data/` directory.

## PDF invoice import

Supported Copel DANF3E PDFs are processed **in server memory** by the local pypdf library. The app does not write the original invoice or raw extracted text to disk, and does not contact Copel or any external API. The persisted tariff fields include price, kWh, invoice total, source (`copel_pdf`) and possibly reference month. Customer names, CPF, addresses, account numbers and payment barcodes are not exported or saved by this importer.

The Streamlit uploader transmits the PDF from the browser to the **Streamlit server**. The bundled launcher keeps that server on `127.0.0.1`; deploying this app remotely changes that privacy property. Do not deploy it publicly without access control.

## GitHub Pages browser edition

The separate GitHub Pages distribution does **not** run a shared Python server. It uses Stlite and Pyodide inside the visitor's browser. `data_directory()` selects an IndexedDB-backed virtual path (`/mnt/energy-usage-estimator`) for that runtime. Files and backups are per browser profile and origin, and they are lost when the browser clears site storage. Export a full JSON backup regularly.

Copel PDF bytes are parsed in browser memory rather than sent to a server. The published site includes only code and static files, not the owner's invoices, JSON dataset, sample user exports, or secrets. Runtime dependencies are downloaded from third-party CDNs (which may receive network metadata such as IP address). Public GitHub Pages does not add account management or cross-device synchronization. See [GitHub Pages guide](github-pages.md).
