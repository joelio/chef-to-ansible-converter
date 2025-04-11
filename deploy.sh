#!/bin/bash

# Deploy script for Chef to Ansible Converter

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

# Check if Heroku CLI is installed
if ! command -v heroku &> /dev/null; then
    echo "Heroku CLI is not installed. Please install it first:"
    echo "https://devcenter.heroku.com/articles/heroku-cli"
    exit 1
fi

# Check if user is logged in to Heroku
if ! heroku auth:whoami &> /dev/null; then
    echo "Please log in to Heroku:"
    heroku login
fi

# Create Heroku app if it doesn't exist
if ! heroku apps:info chef-to-ansible &> /dev/null; then
    echo "Creating Heroku app..."
    heroku create chef-to-ansible
fi

# Set environment variables
echo "Setting environment variables..."
heroku config:set ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY

# Deploy to Heroku
echo "Deploying to Heroku..."
git push heroku master

echo "Deployment complete! Your app should be available at:"
echo "https://chef-to-ansible.herokuapp.com/"
