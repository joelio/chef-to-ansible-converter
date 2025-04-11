#!/bin/bash

# Deploy script for Chef to Ansible Converter to Netlify

# Check if Netlify CLI is installed
if ! command -v netlify &> /dev/null; then
    echo "Netlify CLI is not installed. Please install it first:"
    echo "npm install -g netlify-cli"
    exit 1
fi

# Check if ANTHROPIC_API_KEY is set
if [ -z "$ANTHROPIC_API_KEY" ]; then
    if [ -f .env ]; then
        echo "Loading ANTHROPIC_API_KEY from .env file..."
        export $(grep -v '^#' .env | xargs)
    else
        echo "Error: ANTHROPIC_API_KEY environment variable is not set."
        echo "Please set it with: export ANTHROPIC_API_KEY=your_api_key"
        exit 1
    fi
fi

# Create dist directory if it doesn't exist
mkdir -p dist

# Copy static files to dist
echo "Copying static files to dist directory..."
cp -r web/static/* dist/

# Ensure the images directory exists
mkdir -p dist/images

# Copy the SVG image to the images directory
cp web/static/images/abstract__geometric__8000.svg dist/images/

# Build the project
echo "Building the project..."
npm run build

# Initialize Netlify site if needed
if [ ! -f .netlify/state.json ]; then
    echo "Initializing Netlify site..."
    netlify sites:create --name chef-to-ansible-converter
fi

# Set environment variables
echo "Setting environment variables on Netlify..."
netlify env:set ANTHROPIC_API_KEY "$ANTHROPIC_API_KEY"

# Deploy to Netlify
echo "Deploying to Netlify..."
netlify deploy --prod

echo "Deployment complete!"
