# Package Manifest

## Code

- `scripts/00_check_environment.py`
- `scripts/00_download_raw_datasets.py`
- `scripts/01_prepare_boundaries.py`
- `scripts/02_download_osm_network.py`
- `scripts/03_clean_chargers.py`
- `scripts/04_build_activity_anchors.py`
- `scripts/05_transition_need.py`
- `scripts/06_compute_aaca.py`
- `scripts/07_equity_diagnostics.py`
- `scripts/08_candidate_siting.py`
- `scripts/09_milp_scenarios.py`
- `scripts/10_robustness.py`
- `scripts/11_make_figures_tables.py`
- `scripts/12_run_experiment_suite.py`
- `scripts/13_make_cities_storyline_figures.py`
- `scripts/14_download_mobility_pattern_enrichment.py`
- `scripts/15_build_counterfactual_candidate_universe.py`
- `scripts/16_make_counterfactual_figures.py`
- `scripts/17_make_cities_final_story_maps.py`
- `scripts/18_make_cities_evidence_stack.py`
- `scripts/19_make_cities_methodology_figure.py`
- `scripts/20_make_cities_current_city_figure.py`
- `scripts/21_make_cities_development_atlas.py`
- `scripts/22_make_cities_delta_figure.py`
- `scripts/23_make_method_tables.py`
- `scripts/aaca_utils.py`

## Configuration

- `config/data_catalog.yml`
- `config/experiment_suite.yml`
- `config/parameters.yml`
- `environment.yml`

## Data

- `data_raw/`: redistributable raw public extracts used by the workflow.
- `data_processed/`: processed layers and tables required to reproduce the figures, scenario summaries, and robustness tables.

## Outputs

- `outputs/figures/`: publication figures produced by the scripts.
- `outputs/tables/`: publication tables and experiment summaries.

## Documentation

- `README.md`
- `REPRODUCIBILITY.md`
- `DATA_SOURCES.md`
- `docs/source_log.md`
- `docs/method_notes.md`
- `docs/epm_public_charging_use_audit.md`
- `checksums.sha256`
