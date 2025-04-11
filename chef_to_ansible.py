#!/usr/bin/env python3
"""
Chef to Ansible Converter
A tool that leverages Anthropic's Claude API to convert Chef cookbooks to Ansible playbooks.
"""

import os
import sys
import click
from pathlib import Path

from src.repo_handler import GitRepoHandler
from src.chef_parser import ChefParser
from src.llm_converter import LLMConverter
from src.ansible_generator import AnsibleGenerator
from src.validator import AnsibleValidator
from src.config import Config

@click.group()
def cli():
    """Chef to Ansible Converter CLI"""
    pass

@cli.command()
@click.option('--repo-url', required=True, help='URL of the Git repository containing Chef cookbooks')
@click.option('--output-dir', required=True, help='Directory to output the converted Ansible code')
@click.option('--api-key', envvar='ANTHROPIC_API_KEY', help='Anthropic API key')
@click.option('--model', default='claude-3-opus-20240229', help='Anthropic model to use')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
def convert(repo_url, output_dir, api_key, model, verbose):
    """Convert a Chef repository to Ansible"""
    if not api_key:
        click.echo("Error: Anthropic API key is required. Set it with --api-key or ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)
    
    config = Config(api_key=api_key, model=model, verbose=verbose)
    converter = ChefToAnsibleConverter(config)
    
    try:
        result = converter.convert_repository(repo_url, output_dir)
        click.echo(f"Conversion completed with {result['success_count']} successful conversions")
        if result['failed_count'] > 0:
            click.echo(f"Failed to convert {result['failed_count']} items")
    except Exception as e:
        click.echo(f"Error during conversion: {str(e)}")
        sys.exit(1)

class ChefToAnsibleConverter:
    """Main class for converting Chef cookbooks to Ansible playbooks"""
    
    def __init__(self, config):
        """Initialize the converter with the given configuration"""
        self.config = config
        self.repo_handler = GitRepoHandler()
        self.chef_parser = ChefParser()
        self.llm_converter = LLMConverter(config)
        self.ansible_generator = AnsibleGenerator()
        self.validator = AnsibleValidator()
    
    def convert_repository(self, git_url, output_path):
        """Convert a Chef repository to Ansible"""
        # Create output directory if it doesn't exist
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Clone the repository
        if self.config.verbose:
            click.echo(f"Cloning repository {git_url}...")
        repo_path = self.repo_handler.clone_repository(git_url)
        
        # Find all cookbooks in the repository
        if self.config.verbose:
            click.echo("Finding cookbooks...")
        cookbooks = self.chef_parser.find_cookbooks(repo_path)
        
        if not cookbooks:
            click.echo("No cookbooks found in the repository.")
            self.repo_handler.cleanup(repo_path)
            return {
                'success_count': 0,
                'failed_count': 0,
                'details': []
            }
        
        if self.config.verbose:
            click.echo(f"Found {len(cookbooks)} cookbooks: {', '.join([c['name'] for c in cookbooks])}")
        
        results = {
            'success_count': 0,
            'failed_count': 0,
            'details': []
        }
        
        for i, cookbook in enumerate(cookbooks):
            try:
                if self.config.verbose:
                    click.echo(f"Converting cookbook {i+1}/{len(cookbooks)}: {cookbook['name']}...")
                
                # Parse the cookbook
                parsed_cookbook = self.chef_parser.parse_cookbook(cookbook['path'])
                
                if not parsed_cookbook['recipes']:
                    if self.config.verbose:
                        click.echo(f"No recipes found in cookbook {cookbook['name']}, skipping...")
                    continue
                
                if self.config.verbose:
                    click.echo(f"Found {len(parsed_cookbook['recipes'])} recipes in cookbook {cookbook['name']}")
                
                # Convert the cookbook to Ansible
                ansible_code = self.llm_converter.convert_cookbook(parsed_cookbook)
                
                # Generate Ansible files
                ansible_path = output_dir / cookbook['name']
                self.ansible_generator.generate_ansible_role(ansible_code, ansible_path)
                
                # Validate the generated Ansible code
                validation_result = self.validator.validate(ansible_path)
                
                results['details'].append({
                    'cookbook': cookbook['name'],
                    'success': validation_result['valid'],
                    'messages': validation_result['messages']
                })
                
                if validation_result['valid']:
                    results['success_count'] += 1
                    if self.config.verbose:
                        click.echo(f"Successfully converted cookbook {cookbook['name']}")
                else:
                    results['failed_count'] += 1
                    if self.config.verbose:
                        click.echo(f"Cookbook {cookbook['name']} converted with validation issues: {validation_result['messages']}")
            
            except Exception as e:
                if self.config.verbose:
                    click.echo(f"Error converting cookbook {cookbook['name']}: {str(e)}")
                
                results['details'].append({
                    'cookbook': cookbook['name'],
                    'success': False,
                    'messages': [str(e)]
                })
                results['failed_count'] += 1
        
        # Clean up temporary files
        self.repo_handler.cleanup(repo_path)
        
        return results

if __name__ == '__main__':
    cli()
