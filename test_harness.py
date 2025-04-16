#!/usr/bin/env python3
"""
Test Harness for Chef to Ansible Converter

This script creates a comprehensive test harness that:
1. Fetches Chef examples from GitHub
2. Converts them to Ansible using the converter
3. Validates the converted Ansible code using linting and dry runs
4. Generates a detailed report
"""

import os
import sys
import json
import shutil
import tempfile
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
import yaml
import requests
import git

# Add the parent directory to the path so we can import the converter modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.config import Config
from src.chef_parser import ChefParser
from src.llm_converter import LLMConverter
from src.ansible_generator import AnsibleGenerator
from src.validator import AnsibleValidator

# Define Chef example repositories to test
CHEF_EXAMPLES = [
    {
        "name": "chef-solo-hello-world",
        "url": "https://github.com/binaryphile/chef-solo-hello-world.git",
        "description": "A simple Chef Solo Hello World example"
    },
    {
        "name": "learn-chef-httpd",
        "url": "https://github.com/learn-chef/learn-chef-httpd.git",
        "description": "Learn Chef HTTPD cookbook"
    },
    {
        "name": "chef-nginx",
        "url": "https://github.com/miketheman/nginx.git",
        "description": "Nginx cookbook for Chef"
    }
]

class TestHarness:
    """Test harness for Chef to Ansible converter"""
    
    def __init__(self, api_key=None, model="claude-3-opus-20240229", verbose=True):
        """Initialize the test harness"""
        self.config = Config(api_key=api_key, model=model, verbose=verbose)
        self.chef_parser = ChefParser()
        self.llm_converter = LLMConverter(self.config)
        self.ansible_generator = AnsibleGenerator()
        self.validator = AnsibleValidator(verbose=verbose)
        self.verbose = verbose
        
        # Set up directories
        self.base_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        self.test_repos_dir = self.base_dir / "test-repos"
        self.test_output_dir = self.base_dir / "test-output"
        
        # Create directories if they don't exist
        self.test_repos_dir.mkdir(exist_ok=True)
        if self.test_output_dir.exists():
            shutil.rmtree(self.test_output_dir)
        self.test_output_dir.mkdir()
        
        # Initialize results
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "examples": []
        }
    
    def log(self, message):
        """Log a message if verbose is enabled"""
        if self.verbose:
            print(message)
    
    def clone_chef_examples(self, examples=None):
        """Clone Chef example repositories from GitHub"""
        if examples is None:
            examples = CHEF_EXAMPLES
        
        self.log("\n=== Cloning Chef Examples ===\n")
        
        for example in examples:
            example_dir = self.test_repos_dir / example["name"]
            
            # Skip if already cloned
            if example_dir.exists():
                self.log(f"Example {example['name']} already exists, skipping clone")
                continue
            
            self.log(f"Cloning {example['name']} from {example['url']}...")
            try:
                git.Repo.clone_from(example["url"], example_dir)
                self.log(f"Successfully cloned {example['name']}")
            except Exception as e:
                self.log(f"Error cloning {example['name']}: {str(e)}")
    
    def convert_chef_to_ansible(self, example_name):
        """Convert a Chef example to Ansible"""
        self.log(f"\n=== Converting {example_name} ===\n")
        
        example_dir = self.test_repos_dir / example_name
        output_dir = self.test_output_dir / example_name
        
        # Create output directory
        output_dir.mkdir(exist_ok=True)
        
        # Find cookbooks in the repository
        cookbooks = self.chef_parser.find_cookbooks(example_dir)
        
        if not cookbooks:
            self.log(f"No cookbooks found in {example_name}")
            return {
                "name": example_name,
                "success": False,
                "message": "No cookbooks found",
                "cookbooks": []
            }
        
        self.log(f"Found {len(cookbooks)} cookbooks in {example_name}")
        
        cookbook_results = []
        
        for cookbook in cookbooks:
            cookbook_name = cookbook["name"]
            self.log(f"Converting cookbook: {cookbook_name}")
            
            try:
                # Parse the cookbook
                parsed_cookbook = self.chef_parser.parse_cookbook(cookbook["path"])
                
                if not parsed_cookbook.get("recipes"):
                    self.log(f"No recipes found in cookbook {cookbook_name}, skipping...")
                    cookbook_results.append({
                        "name": cookbook_name,
                        "success": False,
                        "message": "No recipes found",
                        "validation": None
                    })
                    continue
                
                # Convert the cookbook to Ansible
                ansible_data = self.llm_converter.convert_cookbook(parsed_cookbook)
                
                # Generate Ansible role
                role_path = output_dir / cookbook_name
                self.ansible_generator.generate_ansible_role(ansible_data, role_path)
                
                # Validate the generated Ansible code
                validation_result = self.validator.validate_role(role_path)
                
                cookbook_results.append({
                    "name": cookbook_name,
                    "success": validation_result,
                    "message": "Conversion successful" if validation_result else "Validation failed",
                    "validation": self.validator.results
                })
                
                self.log(f"Cookbook {cookbook_name} conversion {'succeeded' if validation_result else 'failed'}")
                
            except Exception as e:
                self.log(f"Error converting cookbook {cookbook_name}: {str(e)}")
                cookbook_results.append({
                    "name": cookbook_name,
                    "success": False,
                    "message": str(e),
                    "validation": None
                })
        
        return {
            "name": example_name,
            "success": any(result["success"] for result in cookbook_results),
            "cookbooks": cookbook_results
        }
    
    def run_ansible_lint(self, role_path):
        """Run ansible-lint on the generated role"""
        self.log(f"Running ansible-lint on {role_path}")
        
        try:
            result = subprocess.run(
                ["ansible-lint", str(role_path)],
                capture_output=True,
                text=True
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e)
            }
    
    def run_ansible_playbook_check(self, role_path):
        """Run ansible-playbook --check on the generated role"""
        self.log(f"Running ansible-playbook --check on {role_path}")
        
        try:
            # Create a temporary directory for testing
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                
                # Create roles directory and symlink the role
                roles_dir = temp_dir_path / "roles"
                roles_dir.mkdir()
                
                role_name = role_path.name
                os.symlink(
                    os.path.abspath(role_path),
                    str(roles_dir / role_name)
                )
                
                # Create inventory file
                with open(temp_dir_path / "inventory", "w") as f:
                    f.write("localhost ansible_connection=local\n")
                
                # Create test playbook
                test_playbook = {
                    "name": f"Test {role_name}",
                    "hosts": "localhost",
                    "roles": [role_name]
                }
                
                with open(temp_dir_path / "test_playbook.yml", "w") as f:
                    yaml.dump([test_playbook], f)
                
                # Run ansible-playbook in check mode
                result = subprocess.run(
                    ["ansible-playbook", "-i", "inventory", "--check", "test_playbook.yml"],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True
                )
                
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr
                }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e)
            }
    
    def run_test_harness(self, examples=None):
        """Run the full test harness"""
        if examples is None:
            examples = [example["name"] for example in CHEF_EXAMPLES]
        
        self.log("\n=== Starting Test Harness ===\n")
        
        # Clone examples if needed
        self.clone_chef_examples()
        
        # Process each example
        for example_name in examples:
            result = self.convert_chef_to_ansible(example_name)
            self.results["examples"].append(result)
        
        # Generate report
        self.generate_report()
        
        return self.results
    
    def generate_report(self):
        """Generate a detailed report of the test harness results"""
        self.log("\n=== Test Harness Report ===\n")
        
        # Calculate summary statistics
        total_examples = len(self.results["examples"])
        successful_examples = sum(1 for example in self.results["examples"] if example["success"])
        
        total_cookbooks = sum(len(example["cookbooks"]) for example in self.results["examples"])
        successful_cookbooks = sum(
            sum(1 for cookbook in example["cookbooks"] if cookbook["success"])
            for example in self.results["examples"]
        )
        
        # Print summary
        self.log(f"Examples: {successful_examples}/{total_examples} successful")
        self.log(f"Cookbooks: {successful_cookbooks}/{total_cookbooks} successful")
        
        # Print detailed results
        for example in self.results["examples"]:
            self.log(f"\nExample: {example['name']}")
            self.log(f"Status: {'✅ Success' if example['success'] else '❌ Failed'}")
            
            for cookbook in example["cookbooks"]:
                self.log(f"  Cookbook: {cookbook['name']}")
                self.log(f"  Status: {'✅ Success' if cookbook['success'] else '❌ Failed'}")
                self.log(f"  Message: {cookbook['message']}")
                
                if cookbook["validation"]:
                    validation = cookbook["validation"]
                    self.log(f"  Validation: {len(validation['passed'])} passed, "
                          f"{len(validation['warnings'])} warnings, "
                          f"{len(validation['errors'])} errors")
        
        # Save report to file
        report_path = self.test_output_dir / "report.json"
        with open(report_path, "w") as f:
            json.dump(self.results, f, indent=2)
        
        self.log(f"\nReport saved to {report_path}")

def main():
    """Main entry point for the test harness"""
    parser = argparse.ArgumentParser(description="Test Harness for Chef to Ansible Converter")
    parser.add_argument("--api-key", help="Anthropic API key")
    parser.add_argument("--model", default="claude-3-opus-20240229", help="Anthropic model to use")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--examples", nargs="+", help="Specific examples to test")
    
    args = parser.parse_args()
    
    # Get API key from environment if not provided
    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    
    if not api_key:
        print("Error: Anthropic API key is required. Set it with --api-key or ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)
    
    # Run test harness
    harness = TestHarness(api_key=api_key, model=args.model, verbose=args.verbose)
    harness.run_test_harness(args.examples)

if __name__ == "__main__":
    main()
