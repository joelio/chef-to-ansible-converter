#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path
from typing import Optional

from src.ansible_generator import AnsibleGenerator
from src.chef_parser import ChefParser
from src.config import Config
from src.llm_converter import LLMConverter
from src.validator import AnsibleValidator

def progress_callback(message: str):
    """Callback function for progress updates"""
    print(f"\r{message}", end='')
    sys.stdout.flush()

def main():
    parser = argparse.ArgumentParser(description='Chef to Ansible Converter')
    parser.add_argument('chef_repo', type=str, help='Path to Chef repository')
    parser.add_argument('--output', type=str, help='Output directory for Ansible roles')
    parser.add_argument('--validate', action='store_true', help='Validate generated roles')
    parser.add_argument('--api-key', type=str, required=True, help='Anthropic API key')
    parser.add_argument('--resource-mapping', type=str, help='Path to custom resource mapping JSON file')
    parser.add_argument('--log-level', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], help='Set logging level')
    
    args = parser.parse_args()
    
    # Initialize configuration
    config = Config(
        api_key=args.api_key,
        verbose=True,
        log_level=args.log_level
    )
    
    # Set custom resource mapping path if provided
    if args.resource_mapping:
        config.resource_mapping_path = args.resource_mapping
    
    # Initialize components
    chef_parser = ChefParser()
    llm_converter = LLMConverter(config, progress_callback=progress_callback)
    ansible_generator = AnsibleGenerator()
    validator = AnsibleValidator()
    
    # Parse Chef repository
    print(f"\nParsing Chef repository at: {args.chef_repo}")
    parsed_cookbooks = chef_parser.parse_repository(args.chef_repo)
    
    if not parsed_cookbooks:
        print("No cookbooks found in repository!")
        sys.exit(1)
    
    # Convert and generate Ansible roles
    output_dir = Path(args.output) if args.output else Path.cwd() / 'ansible_roles'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\nGenerating Ansible roles in: {output_dir}")
    
    for cookbook in parsed_cookbooks:
        print(f"\nProcessing cookbook: {cookbook['name']}")
        
        # Convert to Ansible
        ansible_code = llm_converter.convert_cookbook(cookbook)
        
        # Generate role
        role_path = ansible_generator.generate_role(
            ansible_code,
            output_dir / cookbook['name']
        )
        
        if args.validate:
            print(f"\nValidating role: {cookbook['name']}")
            validation_result = validator.validate(str(role_path))
            if not validation_result['valid']:
                print(f"Validation failed for role: {cookbook['name']}")
                for message in validation_result['messages']:
                    print(f"  - {message}")
                sys.exit(1)
    
    print("\nConversion complete!")

if __name__ == '__main__':
    main()
