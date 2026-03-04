#!/bin/bash
# tile.sh
# Converts GeoJSON files to PMTiles using tippecanoe.
# Requires tippecanoe to be installed.
# Run after prepare_data.py.

set -e  # exit on error

TEMP_DIR="$(pwd)/data/temp"
DOCS_DIR="$(pwd)/docs"

mkdir -p "$DOCS_DIR"
mkdir -p "$TEMP_DIR"

echo "Looking for GeoJSON in: $TEMP_DIR"
ls -lh "$TEMP_DIR/" || echo "temp dir is empty or missing"

echo ""
echo "=== Tiling: criticality network ==="
tippecanoe \
  --output="$DOCS_DIR/criticality.pmtiles" \
  --layer=criticality \
  --minimum-zoom=6 \
  --maximum-zoom=14 \
  --simplification=2 \
  --drop-densest-as-needed \
  --force \
  "$TEMP_DIR/criticality.geojson"

echo ""
echo "=== Tiling: base network ==="
tippecanoe \
  --output="$DOCS_DIR/network.pmtiles" \
  --layer=network \
  --minimum-zoom=5 \
  --maximum-zoom=14 \
  --simplification=2 \
  --drop-densest-as-needed \
  --force \
  "$TEMP_DIR/network.geojson"

echo ""
echo "PMTiles written to $DOCS_DIR/"
ls -lh "$DOCS_DIR/"*.pmtiles
