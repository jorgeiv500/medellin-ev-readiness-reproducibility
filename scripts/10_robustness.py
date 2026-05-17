from __future__ import annotations

from aaca_utils import ROOT, load_yaml


def main() -> None:
    params = load_yaml("config/parameters.yml")
    out = ROOT / "outputs/tables/robustness_plan.csv"
    rows = [
        ("official_only", "Compare official-only charging inventory against cleaned inventory"),
        ("euclidean_vs_network", "Compare straight-line and road-network impedance"),
        ("p_median", "Greedy or MILP p-median baseline"),
        ("max_coverage", "Max coverage baseline"),
        ("bootstrap", f"{params['robustness']['bootstrap_iterations']} UTAM/zone bootstrap iterations"),
        ("random_placebo", f"{params['robustness']['random_placebo_iterations']} random candidate sets"),
        ("ablation", ";".join(params["robustness"]["ablations"])),
        ("pm_congestion", "Use observed PM speed or scenario speed multiplier"),
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("test,description\n" + "\n".join(f"{a},{b}" for a, b in rows), encoding="utf-8")
    print(f"Saved robustness plan to {out}")


if __name__ == "__main__":
    main()

