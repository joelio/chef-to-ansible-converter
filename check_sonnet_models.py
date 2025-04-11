#!/usr/bin/env python3
"""
Script to check for the latest Claude 3 Sonnet model
"""

import os
import sys
import anthropic
from anthropic import Anthropic

def main():
    # Get API key from environment
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)
    
    # Initialize Anthropic client
    client = Anthropic(api_key=api_key)
    
    # Try to list available models directly
    try:
        print("Attempting to list available models from Anthropic API...")
        models = client.models.list()
        print("\nAvailable models:")
        for model in models.data:
            print(f"- {model.id}")
            if "sonnet" in model.id.lower():
                print(f"  ✅ FOUND SONNET MODEL: {model.id}")
    except Exception as e:
        print(f"Error listing models: {str(e)}")
        print("Falling back to testing specific model names...")
        
        # Try specific model names for Claude 3 Sonnet
        sonnet_models = [
            "claude-3-sonnet-20250219",
            "claude-3-sonnet-20250220",
            "claude-3-sonnet-20250221",
            "claude-3-sonnet-20250222",
            "claude-3-sonnet-20250223",
            "claude-3-sonnet-20250224",
            "claude-3-sonnet-20250225",
            "claude-3-sonnet-20250226",
            "claude-3-sonnet-20250227",
            "claude-3-sonnet-20250228",
            "claude-3-sonnet-20250301",
            "claude-3-sonnet-20250302",
            "claude-3-sonnet-20250303",
            "claude-3-sonnet-20250304",
            "claude-3-sonnet-20250305",
            "claude-3-sonnet-20250306",
            "claude-3-sonnet-20250307",
            "claude-3-sonnet-20250308",
            "claude-3-sonnet-20250309",
            "claude-3-sonnet-20250310",
            "claude-3-sonnet-20250311",
            "claude-3-sonnet-20250312",
            "claude-3-sonnet-20250313",
            "claude-3-sonnet-20250314",
            "claude-3-sonnet-20250315",
        ]
        
        for model_name in sonnet_models:
            try:
                print(f"Testing {model_name}...", end=" ")
                client.messages.create(
                    model=model_name,
                    max_tokens=10,
                    messages=[
                        {"role": "user", "content": "Hello"}
                    ]
                )
                print("✓ AVAILABLE")
                print(f"\n✅ FOUND WORKING SONNET MODEL: {model_name}\n")
                return
            except Exception as e:
                error_msg = str(e)
                if "not_found_error" in error_msg:
                    print("✗ Not found")
                else:
                    print(f"✗ Error: {error_msg}")

if __name__ == "__main__":
    main()
