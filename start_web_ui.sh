#!/bin/bash

# Get the API key from environment or prompt the user
API_KEY=${ANTHROPIC_API_KEY}
if [ -z "$API_KEY" ]; then
    echo "ANTHROPIC_API_KEY environment variable not set."
    echo "Please enter your Anthropic API key:"
    read -s API_KEY
fi

# Run the web UI with the API key
python run_web_ui.py --api-key="$API_KEY" --debug --log-level DEBUG --port 5002
