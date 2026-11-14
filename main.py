"""Command-line diagnostics and reproducible calculation without the dashboard."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from energy_estimator.calculations import cost_for_hours, format_brl, format_number, totals, estimate_scenario  # noqa: E402
from energy_estimator.models import Device, Tariff, new_id  # noqa: E402
from energy_estimator.storage import JsonStore, StorageError, data_directory  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    """Execute diagnostics, one-off appliance estimate, or scenario listing."""
    parser = argparse.ArgumentParser(description="Energy Usage Estimator — simulador local de energia elétrica")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("diagnostics", help="Verificar a configuração dos arquivos locais")
    calc = commands.add_parser("estimate", help="Calcular o custo para watts, horas e tarifa informados")
    calc.add_argument("--watts", type=float, required=True)
    calc.add_argument("--hours", type=float, required=True)
    calc.add_argument("--rate", type=float, required=True, help="Tarifa em R$/kWh")
    calc.add_argument("--quantity", type=int, default=1)
    calc.add_argument("--load", type=float, default=100.0, help="Percentual médio da potência nominal (0–100)")
    commands.add_parser("scenarios", help="Listar projeções dos cenários locais com a tarifa salva")
    args = parser.parse_args(argv)

    try:
        if args.command == "estimate":
            rate = Tariff(direct_rate=args.rate).rate
            device = Device(new_id(), "Aparelho", "Simulação", args.watts)
            kwh, cost = cost_for_hours(device, args.hours, rate, quantity=args.quantity, duty_cycle=args.load / 100)
            print(f"Consumo: {format_number(kwh, 4)} kWh | Custo: {format_brl(cost)}")
            return 0
        store = JsonStore(data_directory(ROOT))
        devices, scenarios, tariff = store.load_all()
        if args.command == "diagnostics":
            print(f"Pasta de dados: {store.directory}")
            print(f"Aparelhos: {len(devices)} | Cenários: {len(scenarios)}")
            print(f"Tarifa: R$ {format_number(tariff.rate, 4)}/kWh ({tariff.mode})")
            print("Arquivos JSON válidos.\nExecução: python scripts/launcher.py run")
        else:
            output = []
            for scenario in scenarios:
                summary = totals(estimate_scenario(scenario, devices, tariff.rate))
                output.append({"scenario": scenario.name, **summary})
            print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, StorageError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
