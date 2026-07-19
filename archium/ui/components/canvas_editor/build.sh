#!/bin/bash
# Build script for Canvas Editor component

set -e

echo "Building Canvas Editor component..."
python -m archium.ui.components.canvas_editor.build_frontend "$@"
