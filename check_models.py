#!/usr/bin/env python3
"""
Script to check available models from the Anthropic API with date suffixes
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
    
    # Try different date formats for Claude 3 models
    date_formats = [
        "20240229",  # February 29, 2024
        "20240307",  # March 7, 2024
        "20240219",  # February 19, 2024
        "20240220",  # February 20, 2024
        "20240221",  # February 21, 2024
        "20240222",  # February 22, 2024
        "20240223",  # February 23, 2024
        "20240224",  # February 24, 2024
        "20240225",  # February 25, 2024
        "20240226",  # February 26, 2024
        "20240227",  # February 27, 2024
        "20240228",  # February 28, 2024
        "20240301",  # March 1, 2024
        "20240302",  # March 2, 2024
        "20240303",  # March 3, 2024
        "20240304",  # March 4, 2024
        "20240305",  # March 5, 2024
        "20240306",  # March 6, 2024
    ]
    
    # Models to check
    base_models = [
        "claude-3-opus",
        "claude-3-sonnet",
        "claude-3-haiku"
    ]
    
    print("Checking Anthropic models with date suffixes...")
    
    # Try all combinations
    for base_model in base_models:
        print(f"\nChecking {base_model} with different date suffixes:")
        for date_suffix in date_formats:
            model_name = f"{base_model}-{date_suffix}"
            try:
                print(f"  Testing {model_name}...", end=" ")
                # Just create a simple message to see if the model exists
                client.messages.create(
                    model=model_name,
                    max_tokens=10,
                    messages=[
                        {"role": "user", "content": "Hello"}
                    ]
                )
                print("✓ AVAILABLE")
                # If we get here, the model exists
                print(f"\n✅ FOUND WORKING MODEL: {model_name}\n")
                break
            except Exception as e:
                error_msg = str(e)
                if "not_found_error" in error_msg:
                    print("✗ Not found")
                else:
                    print(f"✗ Error: {error_msg}")

if __name__ == "__main__":
    main()
