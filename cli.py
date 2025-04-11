#!/usr/bin/env python3
"""
CLI for Chef to Ansible Converter
"""

import os
import sys
import argparse
import shutil
import zipfile
from pathlib import Path

from src.config import Config
from src.chef_parser import ChefParser
from src.llm_converter import LLMConverter
from src.ansible_generator import AnsibleGenerator
from src.repo_handler import GitRepoHandler

def convert_cookbook(repo_path, output_path, api_key=None, model=None, verbose=False):
    """
    Convert a Chef cookbook to Ansible roles
    
    Args:
        repo_path (str): Path to the Chef repository
        output_path (str): Path to output the Ansible roles
        api_key (str): Anthropic API key (optional)
        model (str): Anthropic model to use (optional)
        verbose (bool): Enable verbose output
    """
    # Create a config with the provided API key or use environment variable
    if not api_key:
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            print("Error: No API key provided. Please set the ANTHROPIC_API_KEY environment variable or provide it as an argument.")
            sys.exit(1)
    
    config = Config(api_key=api_key)
    if model:
        config.model = model
    config.verbose = verbose
    
    # Create output directory
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Parse the Chef repository
    print(f"Parsing Chef repository at {repo_path}...")
    parser = ChefParser()
    repo_path = Path(repo_path)
    cookbooks = parser.find_cookbooks(repo_path)
    
    if not cookbooks:
        print("No cookbooks found in the repository.")
        return
    
    print(f"Found {len(cookbooks)} cookbooks:")
    for cookbook in cookbooks:
        print(f"  - {cookbook['name']} at {cookbook['path']}")
    
    # Process each cookbook
    for cookbook_info in cookbooks:
        cookbook_path = cookbook_info['path']
        cookbook_name = cookbook_info['name']
        
        print(f"\nProcessing cookbook: {cookbook_name}")
        
        # Parse the cookbook
        cookbook = parser.parse_cookbook(cookbook_path)
        
        # Print cookbook details
        print(f"  - {len(cookbook['recipes'])} recipes")
        print(f"  - {len(cookbook.get('templates', []))} templates")
        print(f"  - {len(cookbook.get('attributes', []))} attribute files")
        
        # Convert the cookbook
        print(f"Converting cookbook {cookbook_name}...")
        converter = LLMConverter(config)
        
        # Skip the actual LLM conversion for templates and just do the ERB to Jinja2 conversion
        ansible_templates = converter.convert_templates(cookbook.get('templates', []))
        
        # Print template details
        print(f"Converted {len(ansible_templates)} templates:")
        for i, template in enumerate(ansible_templates):
            print(f"  - Template {i+1}: {template.get('name', 'N/A')} -> {template.get('path', 'N/A')}")
        
        # Generate Ansible role
        print(f"Generating Ansible role for {cookbook_name}...")
        generator = AnsibleGenerator()
        role_path = output_path / cookbook_name
        
        # Create a simple ansible_data structure for testing
        ansible_data = {
            'name': cookbook_name,
            'tasks': [],  # We're not converting tasks in this test
            'handlers': [],  # We're not converting handlers in this test
            'variables': {},  # We're not converting variables in this test
            'templates': ansible_templates
        }
        
        generator.generate_ansible_role(ansible_data, role_path)
        
        # Check if templates directory exists and has content
        templates_dir = role_path / 'templates'
        print(f"Checking templates directory: {templates_dir}")
        
        if templates_dir.exists():
            template_files = list(templates_dir.glob('**/*'))
            print(f"Templates directory exists with {len(template_files)} files:")
            for file in template_files:
                if file.is_file():
                    print(f"  - {file.relative_to(role_path)}")
        else:
            print("Templates directory does not exist!")
    
    # Create a zip file of the Ansible roles
    print("\nCreating zip file...")
    zip_path = output_path / "ansible_roles.zip"
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(output_path):
            # Skip the zip file itself
            if zip_path.name in files:
                files.remove(zip_path.name)
                
            for file in files:
                file_path = os.path.join(root, file)
                # Calculate the relative path for the zip file
                rel_path = os.path.relpath(file_path, output_path)
                print(f"Adding to zip: {rel_path}")
                zipf.write(file_path, rel_path)
    
    # Check the contents of the zip file
    print(f"\nChecking zip file contents: {zip_path}")
    with zipfile.ZipFile(zip_path, 'r') as zipf:
        zip_contents = zipf.namelist()
        print(f"Zip file contains {len(zip_contents)} files:")
        for file in zip_contents:
            print(f"  - {file}")
    
    print("\nConversion completed successfully!")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Convert Chef cookbooks to Ansible roles')
    parser.add_argument('repo_path', help='Path to the Chef repository')
    parser.add_argument('output_path', help='Path to output the Ansible roles')
    parser.add_argument('--api-key', help='Anthropic API key')
    parser.add_argument('--model', help='Anthropic model to use')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    convert_cookbook(args.repo_path, args.output_path, args.api_key, args.model, args.verbose)

if __name__ == '__main__':
    main()
