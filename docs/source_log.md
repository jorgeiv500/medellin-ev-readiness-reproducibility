# Source Log

Use this file as the audit trail for every dataset. Each entry should include:

- Source name
- URL or portal
- Access date
- License or reuse condition
- Spatial coverage
- Temporal coverage
- Fields retained
- Known limitations
- Script that generated the processed output

## Pending Priority Sources

1. CargaME charger registry for Medellin/Valle de Aburra.
2. EPM public charging stations and charging-use records.
3. UPME charging station layer.
4. OpenChargeMap export.
5. OSM charging stations, roads, POIs, fuel stations, and parking.
6. Encuesta Origen-Destino Valle de Aburra.
7. DANE census and vulnerability variables.
8. SITVA GTFS.
9. GeoMedellin or AMVA activity, safety, POT, parking, and planning layers.
10. DEM for elevation and slope.

## Literature Downloads: Cities

Access date: 2026-05-14.

Special issue target confirmed:

- `Cities` call for papers page: https://www.sciencedirect.com/journal/cities/about/call-for-papers
- Selected special issue: `The challenge of (transitioning to) climate-neutral cities by 2030`
- Submission deadline listed by ScienceDirect: 15 September 2026
- Editorial Manager article type listed by the call: `VSI: climate-NEWtral cities`

Downloaded:

- `data_raw/literature/cities/pdf/cities_2021_urban_governance_autonomous_vehicles.pdf`
  - Article: Grindsted et al. (2022), `Cities`, DOI `10.1016/j.cities.2021.103504`
  - Download source: Roskilde University Research Portal
  - Publisher page: https://www.sciencedirect.com/science/article/pii/S0264275121004030

- `data_raw/literature/cities/pdf/cities_2025_street_review_preprint.pdf`
  - Article: Mushkani and Koseki (2026), `Cities`, DOI `10.1016/j.cities.2025.106602`
  - Download source: arXiv preprint
  - Publisher page: https://www.sciencedirect.com/science/article/pii/S0264275125009059

- `data_raw/literature/cities/pdf/cities_2025_ecosocial_values_urban_green.pdf`
  - Article: Tuomala et al. (2026), `Cities`, DOI `10.1016/j.cities.2025.106592`
  - Download source: UTUPub institutional repository
  - Publisher page: https://www.sciencedirect.com/science/article/pii/S026427512500895X

- `data_raw/literature/cities/pdf/cities_2025_urban_shrinkage_ignoring_denying.pdf`
  - Article: Marjanovic and Lilius (2026), `Cities`, DOI `10.1016/j.cities.2025.106540`
  - Download source: Aalto University Aaltodoc repository
  - Publisher page: https://www.sciencedirect.com/science/article/pii/S0264275125008431

Notes:

- Direct automated PDF download from ScienceDirect was blocked by site controls, even for open-access pages. The local PDFs above come from legal open repositories.
- Closed or unavailable PDFs were not downloaded. Their DOI and publisher pages remain in `data_raw/literature/cities/cities_articles_index.md`.

## Literature Downloads: Closest EV Charging Accessibility and Equity Articles

Access date: 2026-05-14.

Local index:

- `docs/cities_editorial/most_similar_ev_charging_articles.md`
- `data_raw/literature/ev_charging_similarity/literature_manifest.csv`

Downloaded:

- `data_raw/literature/ev_charging_similarity/pdf/trd_2024_opportunity_centric_accessibility_preprint.pdf`
  - Article: Gazmeh, Guo, and Qian (2024), `Transportation Research Part D`, DOI `10.1016/j.trd.2024.104222`
  - Download source: arXiv preprint
  - Publisher page: https://www.sciencedirect.com/science/article/pii/S1361920924001792

- `data_raw/literature/ev_charging_similarity/pdf/trd_2025_en_route_home_proximity_preprint.pdf`
  - Article: Mehditabrizi et al. (2025), `Transportation Research Part D`, DOI `10.1016/j.trd.2025.104910`
  - Download source: arXiv preprint
  - Publisher DOI: https://doi.org/10.1016/j.trd.2025.104910

- `data_raw/literature/ev_charging_similarity/pdf/jtg_2025_london_combined_ev_charger_accessibility.pdf`
  - Article: Zhang and Cao (2025), `Journal of Transport Geography`, DOI `10.1016/j.jtrangeo.2025.104438`
  - Download source: UCL Discovery
  - Repository page: https://discovery.ucl.ac.uk/id/eprint/10215441/

- `data_raw/literature/ev_charging_similarity/pdf/scs_2023_anticipatory_curbside_ev_charging.pdf`
  - Article: Guo and Wang (2023), `Sustainable Cities and Society`, DOI `10.1016/j.scs.2023.104962`
  - Download source: NSF Public Access Repository
  - Publisher DOI: https://doi.org/10.1016/j.scs.2023.104962

- `data_raw/literature/ev_charging_similarity/pdf/nature_2025_equity_reliability_public_evcs_us.pdf`
  - Article: Yu et al. (2025), `Nature Communications`, DOI `10.1038/s41467-025-60091-y`
  - Download source: Nature open-access PDF
  - Article page: https://www.nature.com/articles/s41467-025-60091-y

- `data_raw/literature/ev_charging_similarity/pdf/electricity_journal_2022_inequitable_access_ev_charging_preprint.pdf`
  - Article: Khan et al. (2022), `The Electricity Journal`, DOI `10.1016/j.tej.2022.107096`
  - Download source: arXiv preprint
  - Publisher DOI: https://doi.org/10.1016/j.tej.2022.107096

Metadata only:

- Peng et al. (2024), `Transportation Research Part D`, DOI `10.1016/j.trd.2023.103990`
- Li, Luo, and Song (2022), `Sustainable Cities and Society`, DOI `10.1016/j.scs.2021.103519`
- Carlton and Sultana (2024), `Transportation Research Part D`, DOI `10.1016/j.trd.2024.104123`
- Soltani Mandolakani and Singleton (2024), `Transportation Research Interdisciplinary Perspectives`, DOI `10.1016/j.trip.2024.101072`
- Varghese, Menon, and Ermagun (2024), `Renewable and Sustainable Energy Reviews`, DOI `10.1016/j.rser.2024.114825`
- Uribe et al. (2022), `Revista EIA`, DOI `10.24050/reia.v20i39.1627`
- Sikder, Nagarajan, and Mustafee (2023), `Technological Forecasting and Social Change`, DOI `10.1016/j.techfore.2023.122829`
- Jiao et al. (2025), `Cell Reports Sustainability`, DOI `10.1016/j.crsus.2025.100498`
- Malabanan, Sauri Lavieri, and Mateo-Babiano (2025), `Transport Reviews`, DOI `10.1080/01441647.2025.2502879`
- Ma et al. (2026), `Transportation Research Part D`, DOI `10.1016/j.trd.2026.105307`
- Wijaya et al. (2026), `Transportation Research Interdisciplinary Perspectives`, DOI `10.1016/j.trip.2026.101907`

Notes:

- Direct automated ScienceDirect PDF download was not used where access was blocked or closed. Legal open copies from arXiv, UCL Discovery, NSF PAR, and Nature were retained where available.
- Automated download of the Peng et al. institutional PDF returned a server error.
- Automated download of the Uribe et al. Revista EIA PDF returned a browser challenge; only DOI metadata was retained.

## Raw Dataset Download Batch: Medellin / Valle de Aburra

Access date: 2026-05-14.

Script:

- `scripts/00_download_raw_datasets.py`

Manifest:

- `data_raw/raw_dataset_manifest.csv`

Downloaded or generated:

- CargaME national public charging registry from `https://siveeic.minenergia.gov.co:3011/crg/resumenestacionescarga/0/0`
  - National raw JSON: `data_raw/chargers/cargame_national_raw.json`
  - Valle de Aburra subset: `data_raw/chargers/cargame_valle_aburra_raw.json`
  - Valle de Aburra point GeoJSON: `data_raw/chargers/cargame_valle_aburra.geojson`

- EPM / Datos Abiertos Colombia:
  - EPM public charging use 2019-2025: `data_raw/chargers/epm_public_charging_use_2019_2025.csv`
  - EPM CNG and EV station inventory: `data_raw/chargers/epm_gnv_ev_stations.csv`
  - Metadata: `data_raw/chargers/metadata_bff2-84yc.json`, `data_raw/chargers/metadata_qqm3-dw2u.json`

- AMVA open data:
  - EOD 2017 households, residents, and trips in `data_raw/mobility/eod_valle_aburra/`
  - SIT macrozone and zone shapefile zip: `data_raw/boundaries/amva/zonificacion_macrozona_zonas_sit_shp.zip`
  - The AMVA portal certificate failed local verification, so the script used `verify=False` and recorded the source URL.

- GTFS:
  - Metro Medellin / ColombiaGTFS files in `data_raw/gtfs/metro_medellin/`

- Medellin demographic and vulnerability sources:
  - Projection workbooks from Medellin's population, households, dwellings, barrios/veredas, and deficit page in `data_raw/demographics/medellin/`
  - GeoMedellin ECV indicators in `data_raw/demographics/medellin_arcgis/`
  - Socioeconomic stratum attributes saved as `data_raw/demographics/medellin_arcgis/socioeconomic_stratum_attributes.csv`
  - Stratum geometries were intentionally omitted at this stage because the block-level polygon service is extremely large and unstable for full geometry export.

- GeoMedellin transport, activity, planning, and safety layers:
  - Transport and SITVA-supporting layers in `data_raw/transport/geomedellin/`
  - Activity and facility layers in `data_raw/activity/geomedellin/`
  - POT / planning layers in `data_raw/planning/geomedellin/`
  - 2022 road-safety incident layers in `data_raw/safety/geomedellin/`

- UPME electric planning:
  - National distribution substations layer saved as `data_raw/electric/upme_substations_national_raw.json`
  - The UPME ArcGIS service failed normal `where=1=1` feature export, so the script downloaded records by objectId batches.

- OpenStreetMap / Overpass:
  - EV chargers: `data_raw/osm/overpass_charging_stations.json`
  - Fuel stations: `data_raw/osm/overpass_fuel_stations.json`
  - Parking: `data_raw/osm/overpass_parking.json`
  - Activity anchors: `data_raw/osm/overpass_activity_anchors.json`
  - The initial combined POI query timed out, so the final retained files use split Overpass queries.

- DEM / topography:
  - SRTM/Skadi tiles `N05W076` and `N06W076` saved in `data_raw/topography/`

- OSM drive road network:
  - GraphML saved as `data_processed/road_network.graphml`
  - The network contains 30,689 nodes and 69,995 directed edges after OSMnx simplification and travel-time assignment.
  - `scripts/02_download_osm_network.py` disables OSMnx DNS pinning in this local environment because OSMnx 2.0.6 conflicts with the installed `urllib3-future` resolver signature.

Blocked or pending:

- OpenChargeMap returned HTTP 403 without an API key. Retry with an authenticated key.
- A charger-specific UPME public layer was not located in this batch; CargaME is currently the stronger national charging-registry source.
- Direct DANE CNPV microdata/manzana downloads remain pending; Medellin projection workbooks and ECV indicators are available as interim demographic/vulnerability inputs.
- EPM grid hosting capacity or feeder-level planning data were not found as public open data in this batch.

## Generated Base Maps

Generation date: 2026-05-14.

Script:

- `scripts/11_make_figures_tables.py`

Generated:

- `outputs/figures/fig_cities01_evidence_base_map.png`
  - OD/SIT zones, centralities, Metro/SITVA lines and stations, CargaME/EPM/OSM charging evidence.
- `outputs/figures/fig_cities02_charging_supply_sources.png`
  - Charging-source evidence and candidate universe from OSM fuel and parking features.
- `outputs/figures/fig_cities03_topography_sitva_context.png`
  - SRTM/Skadi elevation context, GTFS SITVA shapes/stops, and charging evidence.
- `outputs/figures/fig_cities04_safety_candidate_context.png`
  - 2022 road-safety incident context, fuel-station candidates, and charging evidence.
- `outputs/figures/fig_cities05_epm_public_use_trend.png`
  - EPM public charging-use trend from the open table.
- `outputs/tables/figure_manifest.csv`

Known limitations:

- These are evidence-base maps, not final AACA/transition-readiness result maps.
- Charger points are not yet spatially deduplicated across sources in these figures.
- Topography is displayed from HGT elevation data as a contextual raster; slope diagnostics still need to be computed for the final model.

Cartographic revision:

- The maps were rebuilt to align the visual sequence with the Medellin-Valle de Aburra argument: current city condition, baseline, scenarios, residual geographies, and baseline-proposal delta.
- The current Medellin maps no longer use an empty white cartographic background.
- The base now uses a light grey analytical canvas, OD/SIT polygon fills, the local OSM drive-road graph, Metro/SITVA linework, scale bars, north arrows, and compact source legends.
- The map-story sequence is documented in `docs/cities_editorial/cities_map_storyboard.md`.
