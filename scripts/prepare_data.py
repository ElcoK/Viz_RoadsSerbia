"""
prepare_data.py

Reads parquet sources, filters columns, simplifies geometries,
and exports GeoJSON files ready for tippecanoe tiling.

Run locally or via GitHub Actions before tiling.
"""

from pathlib import Path
import geopandas as gpd

# =============================================================================
# Paths
# =============================================================================

ROOT         = Path(__file__).parent.parent
DATA_DIR     = ROOT / "data"
TEMP_DIR     = ROOT / "data" / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

print(f"ROOT: {ROOT}")
print(f"TEMP_DIR: {TEMP_DIR}")
print(f"TEMP_DIR exists: {TEMP_DIR.exists()}")

CRITICALITY_PARQUET = DATA_DIR / "Serbia_Criticality.parquet"
NETWORK_PARQUET     = DATA_DIR / "PERS_directed_final.parquet"

CRITICALITY_GEOJSON = TEMP_DIR / "criticality.geojson"
NETWORK_GEOJSON     = TEMP_DIR / "network.geojson"

# =============================================================================
# Columns
# =============================================================================

criticality_cols = [
    'oznaka_deo', 'smer_gdf1', 'kategorija', 'oznaka_put', 'oznaka_poc',
    'naziv_poce', 'oznaka_zav', 'naziv_zavr', 'duzina_deo', 'pocetna_st',
    'zavrsna_st', 'stanje', 'passenger_cars', 'buses', 'light_trucks',
    'medium_trucks', 'heavy_trucks', 'articulated_vehicles', 'total_aadt',
    'road_length', 'average_time_disruption', 'vhl', 'phl', 'thl', 'pkl',
    'tkl', 'flood_depth', 'snow_drift', 'landslide_date', 'hospital_delay',
    'factory_delay', 'police_delay', 'fire_delay', 'port_delay',
    'border_delay', 'railway_delay', 'future_flood_change',
    'future_rainfall_change', 'landslide_exposure',
    'H_hazard_exposure', 'T_travel_disruption', 'A_local_accessibility',
    'CC_climate_criticality', 'H_class', 'T_class', 'A_class', 'CC_class',
    'geometry'
]

network_cols = [
    'oznaka_deo', 'kategorija', 'naziv_poce', 'naziv_zavr',
    'total_aadt', 'road_length', 'speed', 'geometry'
]

# =============================================================================
# Helpers
# =============================================================================

def load_and_prepare(parquet_path, keep_cols):
    print(f"  Reading {parquet_path.name}...")
    gdf = gpd.read_parquet(parquet_path)
    print(f"  {len(gdf)} features loaded")

    # Keep only existing columns (safety check)
    keep = [c for c in keep_cols if c in gdf.columns]
    missing = [c for c in keep_cols if c not in gdf.columns]
    if missing:
        print(f"  WARNING: columns not found and skipped: {missing}")
    gdf = gdf[keep].copy()

    # Reproject to WGS84
    gdf = gdf.to_crs(epsg=4326)

    # Drop null geometries
    gdf = gdf[gdf.geometry.notna()]
    gdf = gdf[~gdf.geometry.is_empty]

    return gdf

def export_geojson(gdf, path):
    print(f"  Exporting to {path.name}...")
    gdf.to_file(str(path), driver="GeoJSON")
    size_mb = path.stat().st_size / 1_000_000
    print(f"  Exported: {size_mb:.1f} MB")

# =============================================================================
# Criticality network
# =============================================================================

print("\n=== Criticality Network ===")
gdf_criticality = load_and_prepare(CRITICALITY_PARQUET, criticality_cols)

# Fill NaN class values
for col in ['H_class', 'T_class', 'A_class', 'CC_class']:
    if col in gdf_criticality.columns:
        gdf_criticality[col] = gdf_criticality[col].fillna('No criticality')

export_geojson(gdf_criticality, NETWORK_GEOJSON)

# =============================================================================
# Base network
# =============================================================================

print("\n=== Base Network ===")
gdf_network = load_and_prepare(NETWORK_PARQUET, network_cols)

# Filter to road categories used in visualisation
road_categories = ['IA', 'IM', 'IB', 'IIA', 'IIB']
gdf_network = gdf_network[gdf_network['kategorija'].isin(road_categories)].copy()
print(f"  {len(gdf_network)} features after category filter")

export_geojson(gdf_network, NETWORK_GEOJSON)

print("\nDone. Ready for tiling.")
