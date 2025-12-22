#!/bin/bash
#
# Example script demonstrating how to use the export_from_neo4j command
#

set -e  # Exit on error

echo "========================================="
echo "Neo4j to YAML Export - Example Script"
echo "========================================="
echo ""

# Set output directory
OUTPUT_DIR="./fabula_export_$(date +%Y%m%d_%H%M%S)"

echo "Configuration:"
echo "  Neo4j URI: bolt://localhost:7689"
echo "  Neo4j User: neo4j"
echo "  Output Directory: $OUTPUT_DIR"
echo ""

# Check if Neo4j is running (optional)
echo "Checking Neo4j connectivity..."
if command -v cypher-shell &> /dev/null; then
    if cypher-shell -u neo4j -p mythology "RETURN 1" &> /dev/null; then
        echo "  ✓ Neo4j is accessible"
    else
        echo "  ✗ Warning: Cannot connect to Neo4j"
        echo "  Make sure Neo4j is running on bolt://localhost:7689"
    fi
else
    echo "  (cypher-shell not found, skipping connectivity check)"
fi
echo ""

# Run the export command
echo "Starting export..."
python manage.py export_from_neo4j \
    --output "$OUTPUT_DIR" \
    --uri "bolt://localhost:7689" \
    --user "neo4j" \
    --password "mythology"

echo ""
echo "========================================="
echo "Export Complete!"
echo "========================================="
echo ""
echo "Output files:"
ls -lh "$OUTPUT_DIR/"
echo ""
echo "Event files:"
ls -1 "$OUTPUT_DIR/events/" | head -n 10
echo ""

# Display manifest summary
if [ -f "$OUTPUT_DIR/manifest.yaml" ]; then
    echo "Export Summary (from manifest.yaml):"
    echo "-----------------------------------"
    grep -E "(series_title|season_count|episode_count|event_count|character_count|connection_count):" "$OUTPUT_DIR/manifest.yaml"
    echo ""
fi

echo "To view a sample event file:"
echo "  cat $OUTPUT_DIR/events/s01e01.yaml"
echo ""
echo "To view character data:"
echo "  cat $OUTPUT_DIR/characters.yaml | head -n 50"
echo ""
echo "Next steps:"
echo "  1. Review the exported files"
echo "  2. Optionally edit YAML files for curation"
echo "  3. Import to Wagtail: python manage.py import_from_yaml --input $OUTPUT_DIR"
echo ""
