<div align="center">
  
# [Energy-Usage-Estimator.](https://github.com/BrenoFariasdaSilva/Energy-Usage-Estimator) <img src="https://github.com/BrenoFariasdaSilva/Energy-Usage-Estimator/blob/d4173c3b2249a77b6b1a223b86e801ea2042eddc/.assets/Icons/GitHub%20Colored%20Icon.svg"  width="3%" height="3%">

<p><strong>Live demo:</strong> <a href="https://brenofariasdasilva.github.io/Energy-Usage-Estimator/">brenofariasdasilva.github.io/Energy-Usage-Estimator</a></p>

</div>

<div align="center">
  
---

**Local-first electricity cost simulator · Python + Streamlit + Plotly · v1.2.0**

Estimate how much your computer, fan, shower, air conditioner, lights, or other appliances cost to run. Save your own appliance catalog and reusable usage scenarios as local JSON files.
  
---

</div>

<div align="center">

![GitHub Code Size in Bytes](https://img.shields.io/github/languages/code-size/BrenoFariasdaSilva/Energy-Usage-Estimator)
![GitHub Commits](https://img.shields.io/github/commit-activity/t/BrenoFariasdaSilva/Energy-Usage-Estimator/main)
![GitHub Last Commit](https://img.shields.io/github/last-commit/BrenoFariasdaSilva/Energy-Usage-Estimator)
![GitHub Forks](https://img.shields.io/github/forks/BrenoFariasdaSilva/Energy-Usage-Estimator)
![GitHub Language Count](https://img.shields.io/github/languages/count/BrenoFariasdaSilva/Energy-Usage-Estimator)
![GitHub License](https://img.shields.io/github/license/BrenoFariasdaSilva/Energy-Usage-Estimator)
![GitHub Stars](https://img.shields.io/github/stars/BrenoFariasdaSilva/Energy-Usage-Estimator)
![GitHub Contributors](https://img.shields.io/github/contributors/BrenoFariasdaSilva/Energy-Usage-Estimator)
![GitHub Created At](https://img.shields.io/github/created-at/BrenoFariasdaSilva/Energy-Usage-Estimator)
![wakatime](https://wakatime.com/badge/github/BrenoFariasdaSilva/Energy-Usage-Estimator.svg)

</div>

<div align="center">
  
![RepoBeats Statistics](https://repobeats.axiom.co/api/embed/2a14dabe65b2dc85fb2636c1752979b5a37f10b9.svg "Repobeats analytics image")

</div>

## Table of Contents
- [Energy-Usage-Estimator. ](#energy-usage-estimator-)
  - [Table of Contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Requirements](#requirements)
  - [Setup](#setup)
    - [Clone the repository](#clone-the-repository)
  - [Installation:](#installation)
    - [Easiest way](#easiest-way)
  - [Run Python Code:](#run-python-code)
    - [Dependencies](#dependencies)
    - [CLI and developer verification](#cli-and-developer-verification)
    - [Typical first session](#typical-first-session)
  - [Supported electricity bill PDFs](#supported-electricity-bill-pdfs)
    - [Copel PDF extraction and fallback priorities](#copel-pdf-extraction-and-fallback-priorities)
    - [Worked example](#worked-example)
  - [Mathematical model](#mathematical-model)
    - [Limitations](#limitations)
  - [Persistent data and privacy](#persistent-data-and-privacy)
    - [Automatic saving, manual save, and recovery](#automatic-saving-manual-save-and-recovery)
  - [How to Cite?](#how-to-cite)
  - [Contributing](#contributing)
  - [Collaborators](#collaborators)
  - [License](#license)
    - [Apache License 2.0](#apache-license-20)

## Introduction

Energy Usage Estimator is an interactive dashboard built in the style and project structure of [GitHub Contribution Analytics](https://github.com/BrenoFariasdaSilva/GitHub-Contribution-Analytics): a Streamlit entry point, an independent `src/` package, CLI, tests, `Makefile`, cross-platform setup helpers and explicit privacy rules.

The interface is in **Brazilian Portuguese (pt-BR)**, values use **R$** and decimal commas, and the billing input is expressed in **R$/kWh** (cost per *kilowatt-hour*, not price per kW/hour). It **does not** integrate with the utility company or read the actual electricity meter. All calculations are estimates based on the entered wattage, usage schedule and price.

## Requirements

- **Python 3.11 or newer**, installed and on PATH. During Python installation on Windows, check **Add Python to PATH**.
- Internet access on **first launch** to install Streamlit, pandas, Plotly and pypdf into `.venv/` (later launches can run offline if dependencies are present).
- A modern browser. Streamlit opens its local dashboard in the browser.
- No database, account, API key, Git configuration, or utility-provider account required.
- Optional: GNU Make for `make` commands.

## Setup

### Clone the repository

1. Clone the repository with the following command:

   ```bash
   git clone https://github.com/BrenoFariasdaSilva/Energy-Usage-Estimator.git
   cd Energy-Usage-Estimator
   ```

Alternatively, download and extract the source ZIP into any folder. Do **not** extract to a protected system folder such as `C:\Program Files`.

## Installation:

The project uses **Python 3.11 or newer**. Its launchers create the virtual environment and install the required packages automatically on first run. No manual `pip install` is necessary.

### Easiest way

| Operating system | Action |
|---|---|
| Windows 10/11 | Double-click `start_windows.bat`. |
| macOS | Double-click `start_macos.command`, or run `sh start_macos.command` from Terminal if execution is restricted. |
| Linux | Run `sh start_linux.sh`. |

The startup script creates `.venv/` if needed, installs the dependencies when the requirements change, and launches Streamlit bound to **127.0.0.1** (only the local computer). The terminal should remain open while using the app; close it or press `Ctrl+C` to stop the server.

## Run Python Code:

To launch the dashboard using the Makefile:

```bash
make run
```

If a terminal is preferred:

**Windows PowerShell:**

```powershell
py -3 scripts/launcher.py run
```

**macOS/Linux:**

```bash
python3 scripts/launcher.py run
```

The browser normally opens at `http://localhost:8501`. If the port is already occupied, Streamlit may choose another one; use the URL printed in the terminal.

### Dependencies

1. To install the application dependencies without opening the dashboard, run:

   ```bash
   make install
   ```

2. Without GNU Make, use the Python launcher (`py -3` on Windows or `python3` on macOS/Linux):

   ```powershell
   py -3 scripts/launcher.py install
   ```

   ```bash
   python3 scripts/launcher.py install
   ```

   The launcher creates `.venv/` and only reinstalls dependencies when the requirements change.

### CLI and developer verification

Run one calculation without the web UI (installed dependencies are not needed for this command):

```bash
python main.py estimate --watts 300 --hours 8 --rate 1.0 --quantity 1 --load 100
```

Run diagnostics and print saved scenario totals:

```bash
python main.py diagnostics
python main.py scenarios
```

Launch developer tests with the provided bootstrap (this installs dev dependencies once):

```bash
python scripts/launcher.py test
```

Or, if `pytest`, `pandas` and `plotly` are already installed:

```bash
python -m pytest -q
```

For source linting after installing `ruff`:

```bash
python -m ruff check .
```

### Typical first session

1. **Início:** Import a supported Copel PDF or manually enter your electricity tariff (default: **R$ 1.00/kWh**).
2. **Aparelhos:** Add your devices or load example appliances. Adjust wattage to match actual specifications.
3. **Calculadora:** Estimate electricity consumption and costs for different usage durations.
4. **Cenários:** Create reusable schedules with multiple appliances, quantities, usage hours/minutes and days per week.
5. **Comparações:** Compare scenarios and estimated savings.
6. **Aparência:** Switch between **Claro** and **Escuro**. Your preference is saved automatically.
7. **Dados e backups:** Save a local JSON checkpoint, download a backup or restore previous data.

For a demo, import `examples/backup-demo.json`. **Warning:** Importing replaces existing data after confirmation.

## Supported electricity bill PDFs

| Document | Support |
|---|---|
| Copel DANF3E/NF3e (verified text-based layout) | **Supported** |
| Copel with missing unit prices but valid total and kWh | **Supported via fallback** |
| Other Copel layouts | **Not guaranteed** |
| Other electricity providers | **Unsupported** |
| Scanned, protected or unreadable PDFs | **Unsupported** |

**Limits:** Maximum 10 MB and 6 pages. Only the first page is analyzed. Processing is local; original PDFs and customer identifiers are not saved.

### Copel PDF extraction and fallback priorities

1. Verify Copel's issuer information, CNPJ, invoice total and billed consumption.
2. **Preferred method:** Add validated, tax-inclusive energy (TE) and distribution (TUSD) unit prices, excluding public lighting.
3. **Fallback:** If unit prices cannot be validated, calculate `total bill ÷ billed kWh`.
4. Preview and confirm the result before applying. Unsupported or rejected PDFs never modify saved settings.

**Example:** For 168 kWh, TE of R$ 0.415476/kWh and TUSD of R$ 0.611012/kWh:

- **Preferred tariff:** R$ 1.026488/kWh.
- **Full-bill average:** R$ 192.72 ÷ 168 = R$ 1.147143/kWh.

### Worked example

A 60 W fan running 8 hours/day at R$ 1.00/kWh consumes **0.48 kWh/day**, costing **R$ 0.48/day** or approximately **R$ 14.40 over 30 days**.

## Mathematical model

**Basic calculation:**

```text
kWh = (watts / 1000) × hours × quantity × load_factor
cost = kWh × tariff_R$/kWh
```

**Scenario projections:**

```text
active_week_kWh = (watts / 1000) × hours_per_day
                  × days_per_week × quantity × load_factor

standby_week_kWh = (standby_watts / 1000)
                   × (168 - active_hours_per_week) × quantity

week_kWh = active_week_kWh + standby_week_kWh
month_kWh = week_kWh × 30 / 7
year_kWh = week_kWh × 365 / 7
cost = kWh × tariff_R$/kWh
```

Standby consumption applies only when enabled. Monthly and annual estimates use average projections rather than exact calendar schedules.

### Limitations

Estimates depend on actual appliance consumption, usage and tariff accuracy. The application does not model complex tariffs, detailed taxation or real-time electricity measurements. Full-bill averages may include fixed charges and therefore differ from marginal electricity costs.

## Persistent data and privacy

All information is stored **locally**, automatically saved after confirmed changes and excluded from Git:

```text
data/
├── devices.json       # Appliances
├── scenarios.json     # Usage scenarios
├── settings.json      # Tariff and appearance
└── backups/           # Local backups
```

Set `ENERGY_ESTIMATOR_DATA_DIR` to use another directory. The `.env.example` file is informational and is not loaded automatically.

Data belongs to the machine running Streamlit, **not browser storage**. The application is intended for local, single-user operation and should not be publicly exposed.

### Automatic saving, manual save, and recovery

- **Automatic:** Confirmed changes to devices, scenarios, tariffs and themes are immediately saved to JSON.
- **Manual:** **Dados e backups → Salvar dados agora** saves all JSON files and creates a timestamped local backup.
- **Export:** **Baixar backup completo (JSON)** downloads a portable backup.
- **Restore:** Validates imported JSON, backs up existing data and restores after confirmation. Older backups default to the light theme.
- **Protection:** Invalid files are not silently overwritten. Unsubmitted form changes are not saved.

The light/dark switch uses application CSS; some native Streamlit components may retain their own appearance.

## How to Cite?

If you use the Energy-Usage-Estimator in your research, please cite it using the following BibTeX entry:

```
@misc{softwareEnergy-Usage-Estimator:2026,
  title = {Energy-Usage-Estimator: Local-first electricity cost simulator · Python + Streamlit + Plotly},
  author = {Breno Farias da Silva},
  year = {2026},
  howpublished = {https://github.com/BrenoFariasdaSilva/Energy-Usage-Estimator},
  note = {Accessed on November 14, 2026}
}
```

You can copy this BibTeX entry into your bibliography file. The source ZIP does not include a separate `main.bib` file.

If you find this repository valuable, please don't forget to give it a ⭐ to show your support! Contributions are highly encouraged, whether by creating issues for feedback or submitting pull requests (PRs) to improve the project. For details on how to contribute, please refer to the [Contributing](#contributing) section below.

Thank you for your support and for recognizing the contribution of this tool to your work!

## Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**. If you have suggestions for improving the code, your insights will be highly welcome.
In order to contribute to this project, please follow the guidelines below or read the [CONTRIBUTING.md](CONTRIBUTING.md) file for more details on how to contribute to this project, as it contains information about the commit standards and the entire pull request process.
Please follow these guidelines to make your contributions smooth and effective:

1. **Set Up Your Environment**: Ensure you've followed the setup instructions in the [Setup](#setup) section to prepare your development environment.

2. **Make Your Changes**:
   - **Create a Branch**: `git checkout -b feature/YourFeatureName`
   - **Implement Your Changes**: Make sure to test your changes thoroughly.
   - **Commit Your Changes**: Use clear commit messages, for example:
     - For new features: `git commit -m "feat(calculator): add daily usage schedule"`
     - For bug fixes: `git commit -m "fix(storage): validate duplicated device IDs"`
     - For documentation: `git commit -m "docs(readme): document bill-derived tariff"`
     - For refactorings: `git commit -m "refactor(charts): reuse period labels"`
     - For tests: `git commit -m "test(calculations): cover standby load"`
   - See more about crafting commit messages in the [CONTRIBUTING.md](CONTRIBUTING.md) file.

3. **Submit Your Contribution**:
   - **Push Your Changes**: `git push origin feature/YourFeatureName`
   - **Open a Pull Request (PR)**: Navigate to the repository on GitHub and open a PR with a detailed description of your changes.

4. **Stay Engaged**: Respond to any feedback from the project maintainers and make necessary adjustments to your PR.

5. **Celebrate**: Once your PR is merged, celebrate your contribution to the project!

## Collaborators

We thank the following people who contributed to this project:

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/BrenoFariasdaSilva" title="Breno Farias da Silva on GitHub">
        <img src="https://github.com/BrenoFariasdaSilva.png" width="100px;" alt="My Profile Picture"/><br>
        <sub>
          <b>Breno Farias da Silva</b>
        </sub>
      </a>
    </td>
  </tr>
</table>

## License

### Apache License 2.0

This project is licensed under the [Apache License 2.0](LICENSE). This license permits use, modification, distribution, and sublicense of the code for both private and commercial purposes, provided that the original copyright notice and a disclaimer of warranty are included in all copies or substantial portions of the software. It also requires a clear attribution back to the original author(s) of the repository. For more details, see the [LICENSE](LICENSE) file in this repository.
