#!/bin/bash

# Deploy script for Chef to Ansible Converter to Render

# Check if RENDER_API_KEY is set
if [ -z "$RENDER_API_KEY" ]; then
    echo "Setting RENDER_API_KEY from command line argument..."
    export RENDER_API_KEY="$1"
    
    if [ -z "$RENDER_API_KEY" ]; then
        echo "Error: RENDER_API_KEY is not set."
        echo "Please set it with: export RENDER_API_KEY=your_api_key"
        echo "Or pass it as an argument: ./deploy-render.sh your_api_key"
        exit 1
    fi
fi

# Check if ANTHROPIC_API_KEY is set
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Error: ANTHROPIC_API_KEY environment variable is not set."
    echo "Please set it with: export ANTHROPIC_API_KEY=your_api_key"
    exit 1
fi

# Initialize Git repository if not already initialized
if [ ! -d ".git" ]; then
    echo "Initializing Git repository..."
    git init
    git add .
    git commit -m "Initial commit for deployment"
fi

# Check if render-cli is installed
if ! command -v render &> /dev/null; then
    echo "render-cli is not installed. Installing now..."
    npm install -g @render/cli
fi

# Deploy to Render
echo "Deploying to Render..."
echo "Using Render API Key: $RENDER_API_KEY"

# Create or update the service using render-cli
render blueprint apply

echo "Setting environment variables..."
curl -X PATCH \
  "https://api.render.com/v1/services/chef-to-ansible/env-vars" \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"envVars\": [{\"key\": \"ANTHROPIC_API_KEY\", \"value\": \"$ANTHROPIC_API_KEY\"}]}"

echo "Deployment initiated! Your app should be available soon at:"
echo "https://chef-to-ansible.onrender.com"
echo "Note: It might take a few minutes for the deployment to complete."
