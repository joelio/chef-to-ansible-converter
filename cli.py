#!/usr/bin/env python3
"""
CLI for Chef to Ansible Converter
"""

import argparse
import os
import sys
import zipfile
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from src.ansible_generator import AnsibleGenerator
from src.chef_parser import ChefParser
from src.config import Config
from src.llm_converter import LLMConverter
from src.validator import AnsibleValidator
from src.logger import setup_logger, logger
from src.repo_handler import GitRepoHandler

def convert_cookbook(repo_path, output_path, api_key=None, model=None, verbose=False, feedback=None, prompt_enhancements=None):
    """
    Convert a Chef cookbook to Ansible roles
    
    Args:
        repo_path (str): Path to the Chef repository
        output_path (str): Path to output the Ansible roles
        api_key (str): Anthropic API key (optional)
        model (str): Anthropic model to use (optional)
        verbose (bool): Enable verbose output
        feedback (str): Path to feedback file from previous conversion (optional)
    """
    # Process feedback content
    feedback_content = None
    
    # First check prompt_enhancements (priority)
    if prompt_enhancements and os.path.isfile(prompt_enhancements):
        try:
            with open(prompt_enhancements, 'r') as f:
                feedback_content = f.read()
            logger.info(f"Using enhanced prompt from previous results ({len(feedback_content)} characters)")
        except Exception as e:
            logger.error(f"Error reading prompt enhancements file: {str(e)}")
    
    # Fall back to feedback file if prompt_enhancements not available
    elif feedback and os.path.isfile(feedback):
        try:
            with open(feedback, 'r') as f:
                feedback_content = f.read()
            logger.info(f"Using feedback from previous conversion ({len(feedback_content)} characters)")
        except Exception as e:
            logger.error(f"Error reading feedback file: {str(e)}")
    
    # Get API key from args or environment variable
    api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        logger.error("No API key provided. Please provide an API key using --api-key or set the ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)
    
    # Initialize configuration
    config = Config(
        api_key=api_key,
        verbose=verbose
    )
    if model:
        config.model = model
    
    # Create output directory
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Parse the Chef repository
    logger.info(f"Parsing Chef repository at: {repo_path}")
    try:
        parser = ChefParser()
        cookbooks = parser.find_cookbooks(repo_path)
    except Exception as e:
        logger.error(f"Failed to parse Chef repository: {str(e)}")
        sys.exit(1)
    
    if not cookbooks:
        logger.error("No cookbooks found in repository!")
        sys.exit(1)
    
    logger.info(f"Found {len(cookbooks)} cookbooks:")
    for cookbook in cookbooks:
        logger.info(f"  - {cookbook['name']} at {cookbook['path']}")
    
    # Process each cookbook
    for cookbook_info in cookbooks:
        cookbook_path = cookbook_info['path']
        cookbook_name = cookbook_info['name']
        
        logger.info(f"Processing cookbook: {cookbook_name}")
        
        try:
            # Parse the cookbook
            parser = ChefParser()
            cookbook = parser.parse_cookbook(cookbook_path)
            
            # Print cookbook details
            logger.info(f"  - {len(cookbook['recipes'])} recipes")
            logger.info(f"  - {len(cookbook.get('templates', []))} templates")
            logger.info(f"  - {len(cookbook.get('attributes', []))} attribute files")
            
            # Convert the cookbook
            logger.info(f"Converting cookbook {cookbook_name}...")
            converter = LLMConverter(config)
            
            # Use the LLM to convert the Chef recipes to Ansible tasks, handlers, and variables
            ansible_data = converter.convert_cookbook(cookbook, feedback_content)
            
            # Also convert templates from ERB to Jinja2
            ansible_templates = converter.convert_templates(cookbook.get('templates', []))
            ansible_data['templates'] = ansible_templates
            
            # Print conversion details
            logger.info(f"Converted {len(ansible_data.get('tasks', []))} tasks")
            logger.info(f"Converted {len(ansible_data.get('handlers', []))} handlers")
            logger.info(f"Converted {len(ansible_data.get('variables', {}))} variables")
            logger.info(f"Converted {len(ansible_templates)} templates:")
            for i, template in enumerate(ansible_templates):
                logger.info(f"  - Template {i+1}: {template.get('name', 'N/A')} -> {template.get('path', 'N/A')}")
            
            # Generate Ansible role
            logger.info(f"Generating Ansible role for {cookbook_name}...")
            generator = AnsibleGenerator()
            role_path = output_path / cookbook_name
            
            generator.generate_ansible_role(ansible_data, role_path)
            
            # Check if templates directory exists and has content
            templates_dir = role_path / 'templates'
            logger.info(f"Checking templates directory: {templates_dir}")
            
            if templates_dir.exists():
                template_files = list(templates_dir.glob('**/*'))
                logger.info(f"Templates directory exists with {len(template_files)} files:")
                for file in template_files:
                    if file.is_file():
                        logger.info(f"  - {file.relative_to(role_path)}")
            else:
                logger.info("Templates directory does not exist!")
        except Exception as e:
            logger.error(f"Failed to convert cookbook {cookbook_name}: {str(e)}")
            continue
    
    # Create a zip file of the Ansible roles
    logger.info("\nCreating zip file...")
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
                logger.info(f"Adding to zip: {rel_path}")
                zipf.write(file_path, rel_path)
    
    # Check the contents of the zip file
    logger.info(f"\nChecking zip file contents: {zip_path}")
    with zipfile.ZipFile(zip_path, 'r') as zipf:
        zip_contents = zipf.namelist()
        logger.info(f"Zip file contains {len(zip_contents)} files:")
        for file in zip_contents:
            logger.info(f"  - {file}")
    
    logger.info("\nConversion complete!")

def main():
    """Main function"""
    # Load environment variables from .env file
    load_dotenv()
    parser = argparse.ArgumentParser(description='Convert Chef cookbooks to Ansible roles')
    parser.add_argument('repo_path', help='Path to the Chef repository')
    parser.add_argument('output_path', help='Path to output the Ansible roles')
    parser.add_argument('--api-key', help='Anthropic API key')
    parser.add_argument('--model', help='Anthropic model to use')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    parser.add_argument('--feedback', help='Path to feedback file from previous conversion')
    parser.add_argument('--prompt-enhancements', help='Path to prompt enhancements based on previous results')
    
    args = parser.parse_args()
    
    convert_cookbook(args.repo_path, args.output_path, args.api_key, args.model, args.verbose, args.feedback, args.prompt_enhancements)

if __name__ == '__main__':
    # Import logging here to avoid circular import issues
    import logging
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nProcess interrupted by user.")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)
