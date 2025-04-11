#!/bin/bash

# Simple deployment script for Render
# This script helps deploy the Chef to Ansible Converter to Render

# Check if curl is installed
if ! command -v curl &> /dev/null; then
    echo "Error: curl is not installed. Please install it first."
    exit 1
fi

# Check if RENDER_API_KEY is set
if [ -z "$1" ] && [ -z "$RENDER_API_KEY" ]; then
    echo "Error: RENDER_API_KEY is not provided."
    echo "Usage: ./deploy-to-render.sh <RENDER_API_KEY>"
    exit 1
fi

# Set the API key
if [ -n "$1" ]; then
    RENDER_API_KEY="$1"
fi

# Check if ANTHROPIC_API_KEY is set
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Error: ANTHROPIC_API_KEY environment variable is not set."
    echo "Please set it with: export ANTHROPIC_API_KEY=your_api_key"
    exit 1
fi

echo "Deploying Chef to Ansible Converter to Render..."

# Create the service on Render
echo "Creating service on Render..."

# Create a temporary JSON file for the service creation request
cat > render-service.json << EOL
{
  "type": "web",
  "name": "chef-to-ansible",
  "env": "python",
  "region": "oregon",
  "plan": "free",
  "buildCommand": "pip install -r requirements.txt",
  "startCommand": "cd web && gunicorn app:app -c ../gunicorn_config.py",
  "envVars": [
    {
      "key": "ANTHROPIC_API_KEY",
      "value": "${ANTHROPIC_API_KEY}"
    },
    {
      "key": "PYTHON_VERSION",
      "value": "3.9.18"
    }
  ]
}
EOL

# Make the API request to create the service
response=$(curl -s -X POST "https://api.render.com/v1/services" \
  -H "Authorization: Bearer ${RENDER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d @render-service.json)

# Check if the service was created successfully
if echo "$response" | grep -q "id"; then
    service_id=$(echo "$response" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
    echo "Service created successfully with ID: $service_id"
    echo "Your application will be available at: https://chef-to-ansible.onrender.com"
    echo "Note: It may take a few minutes for the deployment to complete."
else
    echo "Failed to create service. Response:"
    echo "$response"
    
    # Check if the service already exists
    if echo "$response" | grep -q "already exists"; then
        echo "It seems the service already exists. Trying to update it..."
        
        # Get the list of services to find the ID
        services=$(curl -s -X GET "https://api.render.com/v1/services" \
          -H "Authorization: Bearer ${RENDER_API_KEY}")
        
        # Extract the service ID
        service_id=$(echo "$services" | grep -o '"id":"[^"]*","name":"chef-to-ansible"' | cut -d'"' -f4)
        
        if [ -n "$service_id" ]; then
            echo "Found existing service with ID: $service_id"
            
            # Update the environment variables
            env_vars_response=$(curl -s -X PUT "https://api.render.com/v1/services/${service_id}/env-vars" \
              -H "Authorization: Bearer ${RENDER_API_KEY}" \
              -H "Content-Type: application/json" \
              -d "{\"envVars\":[{\"key\":\"ANTHROPIC_API_KEY\",\"value\":\"${ANTHROPIC_API_KEY}\"}]}")
            
            echo "Environment variables updated. Response:"
            echo "$env_vars_response"
            
            # Trigger a manual deploy
            deploy_response=$(curl -s -X POST "https://api.render.com/v1/services/${service_id}/deploys" \
              -H "Authorization: Bearer ${RENDER_API_KEY}")
            
            echo "Manual deploy triggered. Response:"
            echo "$deploy_response"
            
            echo "Your application will be available at: https://chef-to-ansible.onrender.com"
            echo "Note: It may take a few minutes for the deployment to complete."
        else
            echo "Could not find the existing service. Please check the Render dashboard."
        fi
    fi
fi

# Clean up
rm render-service.json

echo "Deployment process completed!"
