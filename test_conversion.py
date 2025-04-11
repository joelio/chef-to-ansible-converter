#!/usr/bin/env python3
"""
Test script for Chef to Ansible conversion
"""

import os
import sys
from src.config import Config
from src.llm_converter import LLMConverter

def main():
    # Get API key from environment
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)
    
    # Simple Chef recipe to test
    chef_recipe = """
package 'nginx' do
  action :install
end

service 'nginx' do
  action [:enable, :start]
end
    """
    
    # Initialize converter
    config = Config(api_key=api_key, verbose=True)
    converter = LLMConverter(config)
    
    # Convert recipe
    print("Converting Chef recipe to Ansible...")
    print(f"Using model: {config.model}")
    
    try:
        # Create a simple recipe structure
        recipe = {
            'name': 'test',
            'path': 'test.rb',
            'content': chef_recipe
        }
        
        # Convert the recipe
        result = converter.convert_recipe(recipe)
        
        # Print the result
        print("\nConversion successful!")
        print("\nAnsible Tasks:")
        print(result.get('tasks', 'No tasks generated'))
        
        print("\nAnsible Handlers:")
        print(result.get('handlers', 'No handlers generated'))
        
    except Exception as e:
        print(f"Error during conversion: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
