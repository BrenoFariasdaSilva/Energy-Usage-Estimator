<div align="center">
  
# [Energy-Usage-Estimator.](https://github.com/BrenoFariasdaSilva/Energy-Usage-Estimator) <img src="https://github.com/BrenoFariasdaSilva/Energy-Usage-Estimator/blob/d4173c3b2249a77b6b1a223b86e801ea2042eddc/.assets/Icons/GitHub%20Colored%20Icon.svg"  width="3%" height="3%">

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

## License

### Apache License 2.0

This project is licensed under the [Apache License 2.0](LICENSE). This license permits use, modification, distribution, and sublicense of the code for both private and commercial purposes, provided that the original copyright notice and a disclaimer of warranty are included in all copies or substantial portions of the software. It also requires a clear attribution back to the original author(s) of the repository. For more details, see the [LICENSE](LICENSE) file in this repository.
