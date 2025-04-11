#!/usr/bin/env python3
"""
Script to list available models from the Anthropic API
"""

import os
import sys
import anthropic

def main():
    # Get API key from environment
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)
    
    # Initialize Anthropic client
    client = anthropic.Anthropic(api_key=api_key)
    
    try:
        # Print client information
        print(f"Anthropic client version: {anthropic.__version__}")
        print(f"API base URL: {client.base_url}")
        
        # Try to list available models
        print("\nAttempting to get available models...")
        
        # Try to create a message with a model that should exist
        # This is a workaround since there's no direct list_models endpoint
        models_to_try = [
            "claude-3",
            "claude-3-opus",
            "claude-3-sonnet",
            "claude-3-haiku",
            "claude-2",
            "claude-2.0",
            "claude-2.1",
            "claude-instant-1",
            "claude-instant-1.2"
        ]
        
        print("\nTesting models:")
        for model in models_to_try:
            try:
                print(f"Testing model: {model}...", end=" ")
                # Just create a simple message to see if the model exists
                client.messages.create(
                    model=model,
                    max_tokens=10,
                    messages=[
                        {"role": "user", "content": "Hello"}
                    ]
                )
                print("✓ Available")
            except Exception as e:
                print(f"✗ Error: {str(e)}")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
