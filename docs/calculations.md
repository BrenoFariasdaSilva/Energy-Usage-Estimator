# Calculation methodology

The central formula is `energy_kWh = W × h × quantity × duty_fraction / 1000`; cost is `kWh × rate_R$/kWh`.

### Time conventions

- Quick calculations: exact entered hours, independent from weekday schedules, excluding standby.
- A scenario's active weekly duration: `hours_per_day × days_per_week`.
- Weekly energy: active + optional standby for remaining hours of the 168-hour week.
- Monthly: weekly energy × `30/7` — 30-day equivalent, not a calendar month.
- Yearly: weekly energy × `365/7` — 365-day equivalent, not weekday-specific dates.
- Displayed BRL values are rounded to two decimal places; calculations are kept at full floating-point precision until presentation.

### Example: 300 W PC

At R$ 1.00/kWh, 3 hours/day and 5 days/week, at 70% average nominal power:

- Active weekly hours: 15.
- Average active draw: 210 W.
- Weekly energy: 3.15 kWh.
- 30-day energy: 13.5 kWh.
- Monthly cost: R$ 13.50.

If the PC also uses 2 W in standby and is always plugged in, with standby enabled:

- Weekly standby hours: 168 − 15 = 153.
- Weekly standby energy: 0.306 kWh.
- Total weekly energy: 3.456 kWh.
- Monthly cost: 3.456 × 30/7 × 1.00 ≈ R$ 14.81.

### Example: shower

A 5,500 W shower used 15 minutes daily at R$ 1.00/kWh uses:

- 1.375 kWh per day.
- 9.625 kWh per week.
- 41.25 kWh per 30 days.
- R$ 41.25 per 30 days.

### Tariff limitations

The rate calculated from a bill is the effective historical average (`full amount paid / kWh billed`). Costs and credits on a bill can make that different from the rate actually incurred/saved by one marginal kWh. Flat tariff, averaging, single scheduled load fraction and fixed time-duration assumptions are deliberate simplifications; they are not billing-company simulations.

### Importing Copel DANF3E PDFs

For supported text PDFs from Copel Distribuição S.A. (`DANF3E`), the parser extracts the **tax-inclusive unit price** from the two item rows (`ENERGIA ELET CONSUMO` and `ENERGIA ELET USO SISTEMA`) and verifies they reproduce the billed line amounts within R$ 0.03. The preferred marginal proxy is `TE unit price + TUSD unit price`; public lighting is excluded. If either component is missing or inconsistent, the parser uses **Method 2**, `full bill payable / billed kWh`, only when it can unambiguously extract both fields. Unknown utilities, scanned files, inconsistent billed totals or unknown consumption are rejected, not silently guessed.

The result is a projection based on the bill's unit prices, not a guarantee of the utility's future marginal billing rate.
