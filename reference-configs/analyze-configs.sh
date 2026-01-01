#!/bin/bash
# Quick analysis script to show what sections each config contains

echo "==================================="
echo "Klipper Config Section Analysis"
echo "==================================="
echo ""

for cfg in /home/user/gschpoozi/reference-configs/*.cfg; do
    filename=$(basename "$cfg")
    echo ">>> $filename"
    echo "    Sections:"
    grep -E '^\[.*\]' "$cfg" | sed 's/^/      /' | head -20
    echo ""
    echo "    Line count: $(wc -l < "$cfg")"
    echo "    Includes: $(grep -c '^[include ' "$cfg" || echo 0)"
    echo ""
    echo "-----------------------------------"
    echo ""
done

echo ""
echo "==================================="
echo "Section Usage Summary"
echo "==================================="
echo ""
echo "Most common sections across all configs:"
grep -h -E '^\[.*\]' /home/user/gschpoozi/reference-configs/*.cfg | sort | uniq -c | sort -rn | head -20
