#!/usr/bin/env python3

import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.chef_parser import ChefParser
from src.llm_converter import LLMConverter
from src.ansible_generator import AnsibleGenerator
from src.config import Config

# Configuration
COOKBOOK_PATH = Path('/Users/joel/src/work/chef-to-ansible-converter/test_repos/apache2_test/cookbooks/apache2_test')
OUTPUT_DIR = Path('/Users/joel/src/work/chef-to-ansible-converter/test_output')
RESOURCE_MAPPING = Path('/Users/joel/src/work/chef-to-ansible-converter/config/apache2_mappings.json')
# We'll use a placeholder that will be replaced at runtime
API_KEY = ""

# Initialize components
config = Config(
    api_key=API_KEY,
    verbose=True,
    log_level='DEBUG'
)
config.resource_mapping_path = str(RESOURCE_MAPPING)

chef_parser = ChefParser()
llm_converter = LLMConverter(config)
ansible_generator = AnsibleGenerator()

# Parse cookbook
print(f"Parsing cookbook at: {COOKBOOK_PATH}")
cookbook = {
    'name': 'apache2_test',
    'path': COOKBOOK_PATH
}

# Parse recipes from the cookbook
recipes_dir = cookbook['path'] / 'recipes'
recipes = chef_parser._parse_recipes(recipes_dir)
print(f"Found {len(recipes)} recipes")

# Create output directory
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print(f"Generating Ansible roles in: {OUTPUT_DIR}")

# Process each recipe
for recipe in recipes:
    print(f"\nProcessing recipe: {recipe['name']}")
    
    # Convert recipe to Ansible
    ansible_code = llm_converter.convert_recipe(recipe)
    
    # Generate Ansible role
    role_path = ansible_generator.generate_ansible_role(ansible_code, OUTPUT_DIR / cookbook['name'])
    
    print(f"Generated Ansible role at: {role_path}")

print("\nConversion complete!")
