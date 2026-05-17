# Method Notes

Target journal: `Cities`.

The method must be presented as an urban policy and planning instrument, not as a charger-location algorithm alone. Every model output should support a planning interpretation: who lacks everyday public charging access, why the territory produces that disadvantage, and which institution would need to validate the next step.

## Spatial Units

Primary recommendation: OD zones from the Valle de Aburra mobility survey, because they align with trip production and attraction and give the analysis an interpretable metropolitan planning unit.

Sensitivity recommendation: H3 resolution 8 or 9 to reduce dependence on administrative boundaries and support a computational geography framing.

## Medellin Extensions

- Topography: derive mean slope, steep-road share, and elevation range by spatial unit and candidate catchment.
- Metro/SITVA integration: treat metro, cable, tram, BRT, and bus stops as separate anchor categories before collapsing into transit score.
- EPM operations: use public sessions, energy, duration, or utilization fields only where station identifiers and dates can be audited.
- Metropolitan geography: model the valley as a functional region, not only the Medellin municipal boundary.

## Interpretation Boundary

AACA is an accessibility and validation-screening framework. It is not proof of charger uptime, parcel availability, grid hosting capacity, traffic safety, or realized charging demand.
