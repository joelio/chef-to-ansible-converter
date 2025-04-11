#!/usr/bin/env python3
"""
Deploy Chef to Ansible Converter to Render using the Render API
"""

import os
import sys
import json
import requests
import subprocess
import time

# Configuration
RENDER_API_KEY = os.environ.get("RENDER_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
RENDER_API_URL = "https://api.render.com/v1"
SERVICE_NAME = "chef-to-ansible"

def check_environment():
    """Check if required environment variables are set"""
    if not RENDER_API_KEY:
        print("Error: RENDER_API_KEY environment variable is not set.")
        print("Please set it with: export RENDER_API_KEY=your_api_key")
        sys.exit(1)
    
    if not ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY environment variable is not set.")
        print("Please set it with: export ANTHROPIC_API_KEY=your_api_key")
        sys.exit(1)

def init_git_repo():
    """Initialize Git repository if not already initialized"""
    if not os.path.exists(".git"):
        print("Initializing Git repository...")
        subprocess.run(["git", "init"], check=True)
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit for deployment"], check=True)
    else:
        print("Git repository already initialized.")

def create_or_update_service():
    """Create or update the Render service"""
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Check if service exists
    response = requests.get(
        f"{RENDER_API_URL}/services",
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"Error checking services: {response.status_code}")
        print(response.text)
        sys.exit(1)
    
    services = response.json()
    service_exists = any(service["name"] == SERVICE_NAME for service in services)
    
    if service_exists:
        print(f"Service {SERVICE_NAME} already exists. Updating...")
        # For existing services, we'll use deploy hooks
        # Get the service ID
        service_id = next(service["id"] for service in services if service["name"] == SERVICE_NAME)
        
        # Update environment variables
        env_vars_data = {
            "envVars": [
                {"key": "ANTHROPIC_API_KEY", "value": ANTHROPIC_API_KEY}
            ]
        }
        
        response = requests.patch(
            f"{RENDER_API_URL}/services/{service_id}/env-vars",
            headers=headers,
            json=env_vars_data
        )
        
        if response.status_code != 200:
            print(f"Error updating environment variables: {response.status_code}")
            print(response.text)
            sys.exit(1)
        
        print("Environment variables updated successfully.")
        
        # Trigger a manual deploy
        response = requests.post(
            f"{RENDER_API_URL}/services/{service_id}/deploys",
            headers=headers
        )
        
        if response.status_code != 201:
            print(f"Error triggering deploy: {response.status_code}")
            print(response.text)
            sys.exit(1)
        
        deploy_id = response.json().get("id")
        print(f"Deploy triggered with ID: {deploy_id}")
        
    else:
        print(f"Creating new service: {SERVICE_NAME}...")
        
        # Read render.yaml to get service configuration
        with open("render.yaml", "r") as f:
            render_config = f.read()
        
        # Create new service
        service_data = {
            "name": SERVICE_NAME,
            "type": "web",
            "env": "python",
            "region": "oregon",
            "branch": "main",
            "buildCommand": "pip install -r requirements.txt",
            "startCommand": "cd web && gunicorn app:app --log-file -",
            "envVars": [
                {"key": "ANTHROPIC_API_KEY", "value": ANTHROPIC_API_KEY},
                {"key": "PYTHON_VERSION", "value": "3.9.18"}
            ],
            "autoDeploy": "yes"
        }
        
        response = requests.post(
            f"{RENDER_API_URL}/services",
            headers=headers,
            json=service_data
        )
        
        if response.status_code != 201:
            print(f"Error creating service: {response.status_code}")
            print(response.text)
            sys.exit(1)
        
        service_id = response.json().get("id")
        print(f"Service created with ID: {service_id}")

def main():
    """Main function"""
    print("Deploying Chef to Ansible Converter to Render...")
    
    # Check environment variables
    check_environment()
    
    # Initialize Git repository
    init_git_repo()
    
    # Create or update Render service
    create_or_update_service()
    
    print("\nDeployment initiated!")
    print(f"Your app should be available soon at: https://{SERVICE_NAME}.onrender.com")
    print("Note: It might take a few minutes for the deployment to complete.")

if __name__ == "__main__":
    main()
