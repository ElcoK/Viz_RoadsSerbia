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
#print("Simplifying geometries...")
#gdf.geometry = gdf.geometry.simplify(tolerance=0.0001, preserve_topology=True)
#print("  Done")

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

custom_control = """
<style>
/* Hide default Folium layer control */
.leaflet-control-layers {
    display: none !important;
}

/* Header */
#map-header {
    position: fixed;
    top: 0; left: 0; right: 0;
    z-index: 2000;
    background: #1a3a5c;
    color: white;
    padding: 10px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 2px 6px rgba(0,0,0,0.4);
    font-family: Arial, sans-serif;
}
#map-header h1 {
    margin: 0;
    font-size: 16px;
    font-weight: bold;
    letter-spacing: 0.3px;
}
#info-btn {
    background: rgba(255,255,255,0.2);
    border: 1px solid rgba(255,255,255,0.5);
    color: white;
    border-radius: 50%;
    width: 28px;
    height: 28px;
    font-size: 14px;
    font-weight: bold;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
#info-btn:hover {
    background: rgba(255,255,255,0.35);
}

/* Footer */
#map-footer {
    position: fixed;
    bottom: 0; left: 0; right: 0;
    z-index: 2000;
    background: #f5f5f5;
    border-top: 1px solid #ddd;
    padding: 6px 16px;
    font-size: 11px;
    color: #666;
    font-family: Arial, sans-serif;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

/* Push map content below header */
.leaflet-container {
    margin-top: 44px !important;
    height: calc(100vh - 44px) !important;
}

/* Layer control panel */
#layer-control {
    position: fixed;
    top: 80px;
    right: 10px;
    z-index: 1000;
    background: white;
    padding: 12px 16px;
    border-radius: 8px;
    box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
    min-width: 200px;
    font-family: Arial, sans-serif;
}
#layer-control h4 {
    margin: 0 0 10px 0;
    font-size: 13px;
    font-weight: bold;
    border-bottom: 1px solid #eee;
    padding-bottom: 6px;
}
#layer-control label {
    display: block;
    margin-bottom: 6px;
    font-size: 12px;
    cursor: pointer;
}
#layer-control input {
    margin-right: 6px;
    cursor: pointer;
}

/* Legend */
#map-legend {
    position: fixed;
    bottom: 36px;
    right: 10px;
    z-index: 1000;
    background: white;
    padding: 12px 16px;
    border-radius: 8px;
    box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
    min-width: 180px;
    font-family: Arial, sans-serif;
}
#map-legend h4 {
    margin: 0 0 10px 0;
    font-size: 13px;
    font-weight: bold;
    border-bottom: 1px solid #eee;
    padding-bottom: 6px;
}
.legend-item {
    display: flex;
    align-items: center;
    margin-bottom: 5px;
}
.legend-swatch {
    width: 30px;
    height: 4px;
    border: 1px solid #aaa;
    margin-right: 8px;
    flex-shrink: 0;
}
.legend-label {
    font-size: 12px;
}

/* Info modal overlay */
#info-overlay {
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    z-index: 3000;
    background: rgba(0,0,0,0.5);
    align-items: center;
    justify-content: center;
}
#info-overlay.active {
    display: flex;
}
#info-modal {
    background: white;
    border-radius: 10px;
    padding: 28px;
    max-width: 540px;
    width: 90%;
    max-height: 80vh;
    overflow-y: auto;
    font-family: Arial, sans-serif;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    position: relative;
}
#info-modal h2 {
    margin: 0 0 16px 0;
    font-size: 16px;
    color: #1a3a5c;
    border-bottom: 2px solid #1a3a5c;
    padding-bottom: 8px;
}
#info-modal h3 {
    font-size: 13px;
    color: #1a3a5c;
    margin: 16px 0 6px 0;
}
#info-modal p, #info-modal li {
    font-size: 12px;
    color: #444;
    line-height: 1.6;
    margin: 0 0 6px 0;
}
#info-modal ul {
    padding-left: 18px;
    margin: 0 0 8px 0;
}
#close-modal {
    position: absolute;
    top: 12px; right: 16px;
    background: none;
    border: none;
    font-size: 20px;
    cursor: pointer;
    color: #888;
}
#close-modal:hover { color: #333; }
</style>

<!-- Header -->
<div id="map-header">
    <h1>Interactive Visualisation of Serbia's Blue Spot Analysis</h1>
    <button id="info-btn" onclick="document.getElementById('info-overlay').classList.add('active')">i</button>
</div>

<!-- Footer -->
<div id="map-footer">
    <span>&#9432; This tool is intended for exploratory purposes only. All background code can be found here: https://github.com/VU-IVM/Criticality-Analysis-Roads-Serbia. </span>
    <span>Vrije Universiteit Amsterdam &copy; OpenStreetMap contributors &copy; CARTO</span>
</div>

<!-- Info Modal -->
<div id="info-overlay" onclick="if(event.target===this) this.classList.remove('active')">
    <div id="info-modal">
        <button id="close-modal" onclick="document.getElementById('info-overlay').classList.remove('active')">&times;</button>
        <h2>About This Map</h2>

        <h3>&#128214; Methodology</h3>
        <p>This visualisation presents a multi-criteria criticality assessment of Serbia's road network under climate-related hazards (blue spots). Road segments are scored across three dimensions and combined into an overall climate criticality index:</p>
        <ul>
            <li><strong>Hazard Exposure (H):</strong> degree to which a segment is exposed to natural hazards</li>
            <li><strong>Travel Disruption (T):</strong> impact on national-scale connectivity if the segment is disrupted</li>
            <li><strong>Local Accessibility (A):</strong> importance of the segment for local community access</li>
            <li><strong>Climate Criticality (CC):</strong> combined mean score across H, T, and A indicators</li>
        </ul>
        <p>Each indicator is classified into quintiles: <em>Very Low, Low, Medium, High, Very High</em>. Segments with a score of zero are classified as <em>No criticality</em>.</p>

        <h3>&#128506; How to Use</h3>
        <ul>
            <li>Use the <strong>layer panel</strong> (top right) to switch between the four indicators</li>
            <li><strong>Hover</strong> over any road segment to see its scores and classification</li>
            <li><strong>Zoom and pan</strong> freely to explore different parts of Serbia</li>
            <li>The <strong>legend</strong> (bottom right) updates automatically with the active layer</li>
        </ul>

        <h3>&#9888;&#65039; Disclaimer</h3>
        <p>This tool is intended for exploratory purposes only. All background code can be found here: https://github.com/VU-IVM/Criticality-Analysis-Roads-Serbia </p>
    </div>
</div>

<!-- Layer switcher -->
<div id="layer-control">
    <h4>Map Layers</h4>
    <label><input type="radio" name="layer" value="0" checked> Hazard Exposure</label>
    <label><input type="radio" name="layer" value="1"> Travel Disruption</label>
    <label><input type="radio" name="layer" value="2"> Local Accessibility</label>
    <label><input type="radio" name="layer" value="3"> Climate Criticality</label>
</div>

<!-- Legend -->
<div id="map-legend">
    <h4 id="legend-title">Hazard Exposure</h4>
</div>

<script>
var htaColors = {
    'No criticality': '#e0e0e0',
    'Very Low':       '#edf8fb',
    'Low':            '#b3cde3',
    'Medium':         '#8c96c6',
    'High':           '#8856a7',
    'Very High':      '#810f7c'
};
var ccColors = {
    'No criticality': '#e0e0e0',
    'Very Low':       '#ffffcc',
    'Low':            '#a1dab4',
    'Medium':         '#41b6c4',
    'High':           '#2c7fb8',
    'Very High':      '#253494'
};
var classLabels  = ['No criticality', 'Very Low', 'Low', 'Medium', 'High', 'Very High'];
var layerNames   = ['Hazard Exposure', 'Travel Disruption', 'Local Accessibility', 'Climate Criticality'];
var layerColors  = [htaColors, htaColors, htaColors, ccColors];

function buildLegend(idx) {
    var colors = layerColors[idx];
    var title  = layerNames[idx];
    var html   = '<h4>' + title + '</h4>';
    classLabels.forEach(function(lbl) {
        html += '<div class="legend-item">' +
                    '<div class="legend-swatch" style="background:' + colors[lbl] + '"></div>' +
                    '<span class="legend-label">' + lbl + '</span>' +
                '</div>';
    });
    document.getElementById('map-legend').innerHTML = html;
}

function switchLayer(idx) {
    var map = Object.values(window).find(v => v && v._leaflet_id && v.eachLayer);
    if (!map) return;

    var layerGroups = [];
    map.eachLayer(function(layer) {
        if (layer.options && layer.options.name) {
            layerGroups.push(layer);
        }
    });

    var order = ['Hazard Exposure', 'Travel Disruption', 'Local Accessibility', 'Climate Criticality'];
    layerGroups.sort(function(a, b) {
        return order.indexOf(a.options.name) - order.indexOf(b.options.name);
    });

    layerGroups.forEach(function(lg, i) {
        if (i === idx) {
            map.addLayer(lg);
        } else {
            map.removeLayer(lg);
        }
    });

    buildLegend(idx);
}

document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        switchLayer(0);
        document.querySelectorAll('input[name="layer"]').forEach(function(radio) {
            radio.addEventListener('change', function() {
                switchLayer(parseInt(this.value));
            });
        });
    }, 800);
});
</script>
"""

m.get_root().html.add_child(folium.Element(custom_control))

folium.LayerControl(collapsed=False).add_to(m)

# =============================================================================
# Save
# =============================================================================

print(f"Saving to {OUTPUT_PATH}...")
m.save(str(OUTPUT_PATH))
print("Done.")