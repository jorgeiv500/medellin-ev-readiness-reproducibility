# Medellin Electric-Mobility Transition Readiness

Standalone reproducible project to assess public electric-vehicle charging readiness in Medellin and the Valle de Aburra. The analysis treats charging infrastructure as an urban planning problem shaped by topography, mobility demand, public transport, household charging constraints, infrastructure evidence, and metropolitan governance.

The repository is organized as an auditable pipeline. Raw public data are retained unchanged where redistribution is permitted, processed layers are created by scripts, and the figures and tables used in the manuscript are written to `outputs/`.

## Research Frame

The paper asks whether public EV charging makes climate-neutral mobility practical across unequal metropolitan territories. Activity-Anchored Charging Accessibility is used as the access component, not as the whole contribution. The Medellin experiment combines:

- Valle de Aburra functional geography: Medellin, Bello, Itagui, Envigado, Sabaneta, and adjacent municipalities where data permit.
- Topography: slope and elevation as access and implementation constraints.
- Metro/SITVA integration: metro, cable, tram, BRT, bus stops, and intermodal anchors.
- EPM evidence: public charging inventory and operational-use evidence where public data are available.
- Implementation screening: land use, parking, safety, electric-planning evidence, and candidate feasibility proxies.

Working title:

`Uneven Access to the Electric-Mobility Transition: Public EV Charging, Spatial Justice, and Climate-Neutral Urban Mobility in Medellin`

Submission target:

- Journal: `Cities`
- Article type: `VSI: climate-NEWtral cities`
- Deadline: 15 September 2026

## Directory Structure

```text
data_raw/           Raw public downloads retained unchanged where permitted
data_processed/     Cleaned geopackages, matrices, and intermediate products
scripts/            Reproducible pipeline steps
outputs/
  figures/          Publication figures
  tables/           Publication tables
paper/              LaTeX manuscript and bibliography
config/             Data catalog, model parameters, and experiment suite
docs/               Source log, method notes, and data-quality notes
tests/              Lightweight tests for utilities and metrics
```

## Quick Start

Create the environment:

```bash
conda env create -f environment.yml
conda activate medellin-aaca
```

Check the environment and inspect the workflow:

```bash
python scripts/00_check_environment.py
python scripts/12_run_experiment_suite.py
```

Run the full standalone pipeline:

```bash
python scripts/12_run_experiment_suite.py --run
```

Run phases manually when debugging:

```bash
python scripts/00_download_raw_datasets.py
python scripts/01_prepare_boundaries.py
python scripts/02_download_osm_network.py
python scripts/03_clean_chargers.py
python scripts/04_build_activity_anchors.py
python scripts/05_transition_need.py
python scripts/06_compute_aaca.py
python scripts/07_equity_diagnostics.py
python scripts/08_candidate_siting.py
python scripts/09_milp_scenarios.py
python scripts/10_robustness.py
python scripts/11_make_figures_tables.py
python scripts/16_make_counterfactual_figures.py
python scripts/17_make_cities_final_story_maps.py
python scripts/18_make_cities_evidence_stack.py
python scripts/19_make_cities_methodology_figure.py
python scripts/20_make_cities_current_city_figure.py
python scripts/21_make_cities_development_atlas.py
python scripts/22_make_cities_delta_figure.py
python scripts/23_make_method_tables.py
```

## Core Outputs

- `data_processed/mapped_amva_zones.gpkg`
- `data_processed/mapped_charger_evidence.gpkg`
- `data_processed/aaca_scores.gpkg`
- `data_processed/readiness_screen.gpkg`
- `data_processed/readiness_story_screen.gpkg`
- `data_processed/candidate_validation_leads.gpkg`
- `data_processed/counterfactual_candidate_universe.gpkg`
- `data_processed/counterfactual_selected_sites.gpkg`
- `data_processed/counterfactual_zone_outcomes.gpkg`
- `outputs/figures/fig_cities00_methodological_design.png`
- `outputs/figures/fig_cities01_current_city_condition.png`
- `outputs/figures/fig_cities03_baseline_to_proposals.png`
- `outputs/figures/fig_cities04_baseline_proposal_delta.png`
- `outputs/tables/*.csv`
- `outputs/tables/*.tex`

## Recommended Execution Order

1. Data inventory and source log.
2. Spatial unit preparation.
3. Charger reconciliation and duplicate screening.
4. Road network and impedance matrix.
5. Activity-anchor scoring.
6. Transition-need and vulnerability indicators.
7. Activity-anchored access and readiness baseline.
8. Equity and residual-geography diagnostics.
9. Candidate universe and implementation screens.
10. Scenario comparison.
11. Robustness and sensitivity checks.
12. Publication figures, tables, and manuscript inputs.
