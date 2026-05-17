# Data Sources

This package uses public-data sources for Medellin and the Valle de Aburra. Raw extracts are retained unchanged where redistribution is permitted. Source licenses and reuse conditions remain with the original data providers.

| Source group | Provider or portal | Role in the experiment | Local path |
| --- | --- | --- | --- |
| Public charging registry | CargaME / Ministerio de Minas y Energia | Public charging evidence and source reconciliation | `data_raw/chargers/` |
| Public charging inventory and use | EPM / Datos Abiertos Colombia | Charging inventory, public-use evidence, and quality audit | `data_raw/chargers/` |
| Mobility survey | AMVA open data | OD/SIT zones, trip structure, mobility-pressure indicators | `data_raw/mobility/` |
| Public transport | Metro Medellin GTFS and GeoMedellin transport layers | SITVA and intermodal activity anchors | `data_raw/gtfs/`, `data_raw/transport/` |
| Road network and POIs | OpenStreetMap | Drive network, charging stations, fuel stations, parking, and activity anchors | `data_raw/osm/` |
| Planning and centralities | GeoMedellin / municipal planning layers | Land-use and implementation-screening proxies | `data_raw/planning/` |
| Demographic and vulnerability evidence | Medellin open data and GeoMedellin ECV indicators | Household, dwelling, vulnerability, and charging-constraint proxies | `data_raw/demographics/` |
| Safety records | GeoMedellin traffic incident layers | Road-safety context for candidate screening | `data_raw/safety/` |
| Electric-planning evidence | UPME public substation layer | Electric-support context where public evidence is available | `data_raw/electric/` |
| Elevation | Open elevation tiles | Slope and topographic burden | `data_raw/topography/` |

The detailed audit trail is in `docs/source_log.md`. The raw dataset manifest is in `data_raw/raw_dataset_manifest.csv`.

## Redistribution Note

The repository provides public-data extracts and derived layers for reproducibility. Users are responsible for checking the original provider terms before reusing or redistributing any source-specific dataset outside this research context.
