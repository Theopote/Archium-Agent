#!/bin/bash
# Build script for Canvas Editor component

set -e

echo "Building Canvas Editor component..."

# Navigate to frontend directory
cd "$(dirname "$0")/frontend"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Build the component
echo "Building React app..."
npm run build

echo "✓ Build complete!"
echo "Build output: frontend/build"
