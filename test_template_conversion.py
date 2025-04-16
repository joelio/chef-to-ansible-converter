#!/usr/bin/env python3
"""
Test script for Chef to Ansible template conversion
"""

import os
import sys
import json
import shutil
from pathlib import Path
import zipfile

# Add the parent directory to the path so we can import the converter modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.config import Config
from src.chef_parser import ChefParser
from src.llm_converter import LLMConverter
from src.ansible_generator import AnsibleGenerator

def test_template_conversion():
    """Test the template conversion process with a real Chef repository"""
    print("Testing template conversion...")
    
    # Set up paths
    repo_path = Path("test-repos/chef-solo-hello-world")
    output_path = Path("test-output")
    
    # Clean up any existing output
    if output_path.exists():
        shutil.rmtree(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Create a config with a dummy API key (not used for this test)
    config = Config(api_key="dummy-api-key")
    
    # Parse the Chef repository
    print(f"\n1. Parsing Chef repository at {repo_path}...")
    parser = ChefParser()
    cookbooks = parser.find_cookbooks(repo_path)
    print(f"Found {len(cookbooks)} cookbooks:")
    for cookbook in cookbooks:
        print(f"  - {cookbook['name']} at {cookbook['path']}")
    
    # Parse the first cookbook
    cookbook = parser.parse_cookbook(cookbooks[0]['path'])
    print(f"\nParsed cookbook: {cookbook['name']}")
    print(f"  - {len(cookbook['recipes'])} recipes")
    print(f"  - {len(cookbook.get('templates', []))} templates")
    
    # Print template details
    print("\n2. Template details:")
    for i, template in enumerate(cookbook.get('templates', [])):
        print(f"\nTemplate {i+1}:")
        print(f"  - Name: {template.get('name', 'N/A')}")
        print(f"  - Path: {template.get('path', 'N/A')}")
        print(f"  - Content: {template.get('content', 'N/A')[:100]}...")
    
    # Convert the templates
    print("\n3. Converting templates...")
    converter = LLMConverter(config)
    ansible_templates = converter.convert_templates(cookbook.get('templates', []))
    
    print(f"\nConverted {len(ansible_templates)} templates:")
    for i, template in enumerate(ansible_templates):
        print(f"\nConverted Template {i+1}:")
        print(f"  - Name: {template.get('name', 'N/A')}")
        print(f"  - Path: {template.get('path', 'N/A')}")
        print(f"  - Content: {template.get('content', 'N/A')[:100]}...")
    
    # Generate Ansible role
    print("\n4. Generating Ansible role...")
    generator = AnsibleGenerator()
    role_path = output_path / cookbook['name']
    
    # Create a simple ansible_data structure
    ansible_data = {
        'name': cookbook['name'],
        'tasks': [],
        'handlers': [],
        'variables': {},
        'templates': ansible_templates
    }
    
    generator.generate_ansible_role(ansible_data, role_path)
    
    # Check if templates directory exists and has content
    templates_dir = role_path / 'templates'
    print(f"\n5. Checking templates directory: {templates_dir}")
    
    if templates_dir.exists():
        template_files = list(templates_dir.glob('**/*'))
        print(f"Templates directory exists with {len(template_files)} files:")
        for file in template_files:
            print(f"  - {file.relative_to(role_path)}")
            # Print the first few lines of each file if it's a regular file
            if file.is_file():
                try:
                    with open(file, 'r') as f:
                        content = f.read(200)
                        print(f"    Content preview: {content[:100]}...")
                except Exception as e:
                    print(f"    Error reading file: {str(e)}")
            else:
                print(f"    [Directory]")
    else:
        print("Templates directory does not exist!")
    
    # Create a zip file of the Ansible role
    print("\n6. Creating zip file...")
    zip_path = output_path / f"{cookbook['name']}.zip"
    
    def zipdir(path, ziph):
        for root, dirs, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                ziph.write(file_path, os.path.relpath(file_path, os.path.join(path, '..')))
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipdir(role_path, zipf)
    
    # Check the contents of the zip file
    print(f"\n7. Checking zip file contents: {zip_path}")
    with zipfile.ZipFile(zip_path, 'r') as zipf:
        zip_contents = zipf.namelist()
        print(f"Zip file contains {len(zip_contents)} files:")
        for file in zip_contents:
            print(f"  - {file}")
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_template_conversion()
