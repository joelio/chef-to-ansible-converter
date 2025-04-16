#!/usr/bin/env python3
"""
Simple script to test the Anthropic API key
"""

import os
import sys
from dotenv import load_dotenv
import anthropic

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Get API key from environment variable
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: No ANTHROPIC_API_KEY environment variable found.")
        sys.exit(1)
    
    print(f"API key found: {api_key[:5]}...{api_key[-4:]}")
    
    # Initialize Anthropic client
    client = anthropic.Anthropic(api_key=api_key)
    
    try:
        # Make a simple API call
        print("Making test API call...")
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            messages=[
                {"role": "user", "content": "Hello, Claude! This is a test message."}
            ]
        )
        
        # If we get here, the API call was successful
        print("API call successful!")
        print(f"Response: {message.content[0].text[:100]}...")
        return True
    except Exception as e:
        print(f"API Error: {str(e)}")
        return False

if __name__ == "__main__":
    main()
