# EPM public charging-use data audit

Status: 2026-05-14

## Source checked

Primary source:

- Datos Abiertos Colombia dataset `bff2-84yc`: `Uso de estaciones de carga pública de EPM para vehículos eléctricos (2019-2025)`.
- API CSV: `https://www.datos.gov.co/resource/bff2-84yc.csv?$limit=500000`
- Metadata API: `https://www.datos.gov.co/api/views/bff2-84yc`
- Count API: `https://www.datos.gov.co/resource/bff2-84yc.json?$select=count(*)`

Related official EPM pages:

- `https://www.epm.com.co/clientesyusuarios/energia/hogar/movilidad-electrica/carga-publica/`
- `https://www.epm.com.co/clientesyusuarios/energia/hogar/movilidad-electrica/`

## Completeness result

The local file is complete for the coverage declared by the official dataset.

- Official coverage stated in metadata: January 2019 to June 2025.
- Expected monthly rows for that coverage: 78.
- API count on 2026-05-14: 78.
- Local rows: 78.
- Latest direct API download rows: 78.
- Local file equals latest direct API download: yes.
- Missing year-month pairs within January 2019-June 2025: 0.

This means the file is not truncated. It is complete for the source's declared temporal coverage, but it is not current through 2026. As of the 2026-05-14 check, the public dataset stops in June 2025.

## Outliers and correction months

The unusual peaks are present in the official source, not introduced by the local pipeline.

Flagged negative-total months:

- July 2020: total = -136,087.
- October 2020: total = -195,525.

Flagged positive spikes:

- June 2020: total = 152,330.
- September 2020: total = 216,123.
- August 2024: total = 85,073.
- December 2024: total = 149,205.

The metadata explicitly warns that some months can present atypical high or low variations due to operational adjustments in reading and billing/settlement processes. Therefore, monthly values should not be interpreted as clean station demand, session demand, occupancy, or connector reliability.

## Files created

- `data_raw/chargers/epm_public_charging_use_latest_check.csv`: latest direct API download used for comparison.
- `data_raw/chargers/metadata_bff2-84yc_latest_check.json`: latest metadata snapshot.
- `outputs/tables/epm_public_charging_use_quality_audit.csv`: machine-readable audit summary.
- `data_processed/epm_public_charging_use_validated.csv`: sorted file with date and flags for source correction months, positive spikes, and partial year.

## Paper implication

Use the EPM series only as aggregate operational evidence that public charging exists and has grown. Do not use it as a monthly behavioral demand signal without correction, smoothing, or operator clarification. The safest visual is annual/cumulative reported use with correction months flagged.
