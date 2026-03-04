from pathlib import Path
import json
import geopandas as gpd
import pandas as pd
import folium
from folium import GeoJson, GeoJsonTooltip

# =============================================================================
# Paths
# =============================================================================

ROOT        = Path(__file__).parent.parent
DATA_PATH   = ROOT / "data" / "Serbia_Criticality.gpkg"
OUTPUT_PATH = ROOT / "docs" / "index.html"

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# =============================================================================
# Load Data
# =============================================================================

print("Loading data...")
gdf = gpd.read_file(DATA_PATH)
gdf = gdf.to_crs(epsg=4326)
print(f"  Loaded {len(gdf)} features")

# Simplify geometries to reduce output HTML size
# tolerance in degrees (~10m at this latitude) — adjust if needed
print("Simplifying geometries...")
gdf.geometry = gdf.geometry.simplify(tolerance=0.0001, preserve_topology=True)
print("  Done")

# =============================================================================
# Classification (CC / mean_class)
# =============================================================================

norm_cols = ['H_hazard_exposure', 'T_travel_disruption', 'A_local_accessibility']

# Only compute if not already in file
if 'criticality_mean' not in gdf.columns:
    print("Computing criticality_mean...")
    gdf['criticality_mean'] = gdf[norm_cols].mean(axis=1)

if 'mean_class' not in gdf.columns:
    print("Computing mean_class...")
    def classify_quintiles(series, labels=None):
        if labels is None:
            labels = ['Very Low', 'Low', 'Medium', 'High', 'Very High']
        result = pd.Series('No criticality', index=series.index)
        non_zero_mask = series > 0
        non_zeros = series[non_zero_mask]
        if not non_zeros.empty:
            bins = pd.qcut(non_zeros, 5, labels=labels, duplicates='drop')
            result[non_zero_mask] = bins.astype(str)
        return result

    gdf['mean_class'] = classify_quintiles(gdf['criticality_mean'])

# =============================================================================
# Configuration
# =============================================================================

labels = ['No criticality', 'Very Low', 'Low', 'Medium', 'High', 'Very High']

hta_colors = {
    'No criticality': '#e0e0e0',
    'Very Low':       '#edf8fb',
    'Low':            '#b3cde3',
    'Medium':         '#8c96c6',
    'High':           '#8856a7',
    'Very High':      '#810f7c'
}

cc_colors = {
    'No criticality': '#e0e0e0',
    'Very Low':       '#ffffcc',
    'Low':            '#a1dab4',
    'Medium':         '#41b6c4',
    'High':           '#2c7fb8',
    'Very High':      '#253494'
}

weight_mapping = {
    'No criticality': 1,
    'Very Low':       1.5,
    'Low':            2,
    'Medium':         2.5,
    'High':           3.5,
    'Very High':      5
}

opacity_mapping = {
    'No criticality': 0.4,
    'Very Low':       0.8,
    'Low':            0.8,
    'Medium':         0.8,
    'High':           0.8,
    'Very High':      0.8
}

layer_config = [
    {'col': 'H_class',    'name': 'Hazard Exposure',      'colors': hta_colors, 'show': True},
    {'col': 'T_class',    'name': 'Travel Disruption',    'colors': hta_colors, 'show': False},
    {'col': 'A_class',    'name': 'Local Accessibility',  'colors': hta_colors, 'show': False},
    {'col': 'mean_class', 'name': 'Climate Criticality',  'colors': cc_colors,  'show': False},
]

popup_cols = [
    'section_id', 'naziv_poc', 'naziv_pov',
    'H_hazard_exposure', 'T_travel_disruption', 'A_local_accessibility',
    'H_class', 'T_class', 'A_class', 'mean_class'
]
popup_cols = [c for c in popup_cols if c in gdf.columns]

# =============================================================================
# Build Map
# =============================================================================

print("Building map...")

m = folium.Map(
    location=[44.0, 21.0],
    zoom_start=7,
    tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> '
         '&copy; <a href="https://carto.com/attributions">CARTO</a>',
    prefer_canvas=True
)

for cfg in layer_config:
    col      = cfg['col']
    cmap     = cfg['colors']
    fg       = folium.FeatureGroup(name=cfg['name'], show=cfg['show'])

    # Draw in order so higher criticality renders on top
    for cat in labels:
        subset = gdf[gdf[col] == cat].copy()
        if subset.empty:
            continue

        print(f"  {cfg['name']} — {cat}: {len(subset)} segments")

        geojson_data = json.loads(subset[popup_cols + ['geometry']].to_json())

        GeoJson(
            geojson_data,
            style_function=lambda feature,
                c=cmap[cat],
                w=weight_mapping[cat],
                o=opacity_mapping[cat]: {
                    'color':   c,
                    'weight':  w,
                    'opacity': o
            },
            tooltip=GeoJsonTooltip(
                fields=popup_cols,
                aliases=[c.replace('_', ' ').title() for c in popup_cols],
                localize=True,
                sticky=True,
                style="font-size: 12px;"
            )
        ).add_to(fg)

    fg.add_to(m)

# =============================================================================
# Legend (dynamic — updates when switching layers)
# =============================================================================

legend_js = """
<script>
function updateLegend() {
    const layerControl = document.querySelector('.leaflet-control-layers');
    if (!layerControl) return;

    const inputs = layerControl.querySelectorAll('input[type=checkbox]');
    const labels_el = layerControl.querySelectorAll('.leaflet-control-layers-base label, .leaflet-control-layers-overlays label');

    const htaColors = {
        'No criticality': '#e0e0e0',
        'Very Low':       '#edf8fb',
        'Low':            '#b3cde3',
        'Medium':         '#8c96c6',
        'High':           '#8856a7',
        'Very High':      '#810f7c'
    };
    const ccColors = {
        'No criticality': '#e0e0e0',
        'Very Low':       '#ffffcc',
        'Low':            '#a1dab4',
        'Medium':         '#41b6c4',
        'High':           '#2c7fb8',
        'Very High':      '#253494'
    };

    const layerColors = {
        'Hazard Exposure':     htaColors,
        'Travel Disruption':   htaColors,
        'Local Accessibility': htaColors,
        'Climate Criticality': ccColors
    };

    const classLabels = ['No criticality', 'Very Low', 'Low', 'Medium', 'High', 'Very High'];

    // Find which layer is currently checked
    let activeLayer = 'Hazard Exposure';
    inputs.forEach((input, i) => {
        if (input.checked && labels_el[i]) {
            const name = labels_el[i].textContent.trim();
            if (layerColors[name]) activeLayer = name;
        }
    });

    const colors = layerColors[activeLayer];
    let items = '';
    classLabels.forEach(lbl => {
        items += `
            <div style="display:flex;align-items:center;margin-bottom:5px;">
                <div style="width:30px;height:4px;background:${colors[lbl]};
                            border:1px solid #aaa;margin-right:8px;"></div>
                <span style="font-size:12px;">${lbl}</span>
            </div>`;
    });

    document.getElementById('map-legend').innerHTML = `
        <div style="font-weight:bold;font-size:13px;margin-bottom:8px;">${activeLayer}</div>
        ${items}`;
}

// Run on load and whenever layer control is clicked
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(updateLegend, 500);
    document.addEventListener('click', function(e) {
        if (e.target.closest('.leaflet-control-layers')) {
            setTimeout(updateLegend, 100);
        }
    });
});
</script>
"""

legend_html = """
<div id="map-legend"
     style="position:fixed; bottom:40px; right:10px; z-index:1000;
            background:white; padding:12px 16px; border-radius:8px;
            box-shadow:2px 2px 6px rgba(0,0,0,0.3); min-width:180px;">
</div>
"""

m.get_root().html.add_child(folium.Element(legend_html + legend_js))
folium.LayerControl(collapsed=False).add_to(m)

# =============================================================================
# Save
# =============================================================================

print(f"Saving to {OUTPUT_PATH}...")
m.save(str(OUTPUT_PATH))
print("Done.")