# Reproducibility Instructions

This package contains the code, configuration, public-data extracts, processed layers, figures, and tables needed to reproduce the Medellin-Valle de Aburra EV charging readiness experiment.

## Environment

Create the conda environment:

```bash
conda env create -f environment.yml
conda activate medellin-aaca
```

Check that the core dependencies are available:

```bash
python scripts/00_check_environment.py
```

## Workflow

Inspect the standalone experiment suite:

```bash
python scripts/12_run_experiment_suite.py
```

Run the full workflow:

```bash
python scripts/12_run_experiment_suite.py --run
```

The workflow is organized into six phases:

1. Public-data foundation.
2. Charging-evidence reconciliation.
3. Urban readiness baseline.
4. Candidate validation universe.
5. Scenario and residual evaluation.
6. Publication figures and tables.

## Key Inputs

- `config/data_catalog.yml`: public source registry and local paths.
- `config/parameters.yml`: model parameters, weights, thresholds, network settings, and scenario definitions.
- `config/experiment_suite.yml`: ordered execution plan.
- `data_raw/`: raw public data retained unchanged where redistribution is permitted.
- `data_processed/`: processed geospatial layers and tables used by the scenario analysis and figures.

## Key Outputs

- `data_processed/readiness_screen.gpkg`
- `data_processed/readiness_story_screen.gpkg`
- `data_processed/candidate_validation_leads.gpkg`
- `data_processed/counterfactual_candidate_universe.gpkg`
- `data_processed/counterfactual_selected_sites.gpkg`
- `data_processed/counterfactual_zone_outcomes.gpkg`
- `outputs/figures/`
- `outputs/tables/`

## Verification

Run the utility tests:

```bash
pytest tests
```

Verify file integrity after download from Zenodo:

```bash
shasum -a 256 -c checksums.sha256
```

## Scope

The package supports computational reproducibility of the reported public-data screen. It does not replace field verification, grid-hosting assessment, road-safety review, parcel control, operator commitment, tariff review, or connector-level service monitoring.
