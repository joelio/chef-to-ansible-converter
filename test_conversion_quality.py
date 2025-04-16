#!/usr/bin/env python3
"""
Test Harness for Chef to Ansible Converter Quality

This script tests the quality of the Chef to Ansible conversion by:
1. Using a real Chef example from GitHub
2. Converting it to Ansible
3. Validating the generated Ansible code with linting and dry-run checks
4. Providing feedback on what needs to be improved in the converter
"""

import os
import sys
import json
import shutil
import tempfile
import subprocess
from pathlib import Path
import yaml
import git

# Add the parent directory to the path so we can import the converter modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.config import Config
from src.chef_parser import ChefParser
from src.llm_converter import LLMConverter
from src.ansible_generator import AnsibleGenerator

# Define Chef example repository
CHEF_EXAMPLE = {
    "name": "chef-solo-hello-world",
    "url": "https://github.com/karmi/chef-solo-hello-world.git",
    "description": "A simple Chef Solo Hello World example"
}

class ConversionQualityTester:
    """Test the quality of Chef to Ansible conversion"""
    
    def __init__(self, api_key=None, verbose=True):
        """Initialize the tester"""
        self.config = Config(api_key=api_key, verbose=verbose)
        self.chef_parser = ChefParser()
        self.llm_converter = LLMConverter(self.config)
        self.ansible_generator = AnsibleGenerator()
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
    
    def log(self, message):
        """Log a message if verbose is enabled"""
        if self.verbose:
            print(message)
    
    def clone_chef_example(self):
        """Clone the Chef example repository from GitHub"""
        example_dir = self.test_repos_dir / CHEF_EXAMPLE["name"]
        
        # Skip if already cloned
        if example_dir.exists():
            self.log(f"Example {CHEF_EXAMPLE['name']} already exists, skipping clone")
            return example_dir
        
        self.log(f"Cloning {CHEF_EXAMPLE['name']} from {CHEF_EXAMPLE['url']}...")
        try:
            git.Repo.clone_from(CHEF_EXAMPLE["url"], example_dir)
            self.log(f"Successfully cloned {CHEF_EXAMPLE['name']}")
        except Exception as e:
            self.log(f"Error cloning {CHEF_EXAMPLE['name']}: {str(e)}")
            raise
        
        return example_dir
    
    def convert_chef_to_ansible(self, example_dir):
        """Convert a Chef example to Ansible"""
        self.log(f"\n=== Converting {CHEF_EXAMPLE['name']} ===\n")
        
        output_dir = self.test_output_dir / CHEF_EXAMPLE["name"]
        output_dir.mkdir(exist_ok=True)
        
        # Find cookbooks in the repository
        cookbooks = self.chef_parser.find_cookbooks(example_dir)
        
        if not cookbooks:
            self.log(f"No cookbooks found in {CHEF_EXAMPLE['name']}")
            return None
        
        self.log(f"Found {len(cookbooks)} cookbooks in {CHEF_EXAMPLE['name']}")
        
        cookbook_results = []
        
        for cookbook in cookbooks:
            cookbook_name = cookbook["name"]
            self.log(f"Converting cookbook: {cookbook_name}")
            
            try:
                # Parse the cookbook
                parsed_cookbook = self.chef_parser.parse_cookbook(cookbook["path"])
                
                if not parsed_cookbook.get("recipes"):
                    self.log(f"No recipes found in cookbook {cookbook_name}, skipping...")
                    continue
                
                # Convert the cookbook to Ansible
                ansible_data = self.llm_converter.convert_cookbook(parsed_cookbook)
                
                # Add name to ansible_data
                ansible_data["name"] = cookbook_name
                
                # Add templates if they exist
                if "templates" in parsed_cookbook:
                    ansible_data["templates"] = self.llm_converter.convert_templates(parsed_cookbook["templates"])
                
                # Generate Ansible role
                role_path = output_dir / cookbook_name
                self.ansible_generator.generate_ansible_role(ansible_data, role_path)
                
                cookbook_results.append({
                    "name": cookbook_name,
                    "path": role_path,
                    "ansible_data": ansible_data
                })
                
                self.log(f"Cookbook {cookbook_name} conversion completed")
                
            except Exception as e:
                self.log(f"Error converting cookbook {cookbook_name}: {str(e)}")
                raise
        
        return cookbook_results
    
    def run_ansible_lint(self, role_path):
        """Run ansible-lint on the generated role"""
        self.log(f"Running ansible-lint on {role_path}")
        
        try:
            result = subprocess.run(
                ["ansible-lint", str(role_path), "--parseable"],
                capture_output=True,
                text=True
            )
            
            # Parse the output
            lint_issues = []
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        lint_issues.append(line)
            
            return {
                "success": result.returncode == 0,
                "issues": lint_issues,
                "raw_output": result.stdout,
                "error": result.stderr
            }
        except Exception as e:
            return {
                "success": False,
                "issues": [str(e)],
                "raw_output": "",
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
    
    def analyze_conversion_issues(self, lint_result, playbook_result):
        """Analyze conversion issues and provide recommendations"""
        issues = {
            "lint": {
                "fqcn": [],  # Fully Qualified Collection Names
                "naming": [],  # Naming conventions
                "truthy": [],  # Truthy values
                "other": []
            },
            "playbook": {
                "undefined_vars": [],
                "syntax": [],
                "other": []
            }
        }
        
        # Analyze lint issues
        if not lint_result["success"]:
            for issue in lint_result["issues"]:
                if "fqcn" in issue:
                    issues["lint"]["fqcn"].append(issue)
                elif "name" in issue and "casing" in issue:
                    issues["lint"]["naming"].append(issue)
                elif "truthy" in issue:
                    issues["lint"]["truthy"].append(issue)
                else:
                    issues["lint"]["other"].append(issue)
        
        # Analyze playbook issues
        if not playbook_result["success"]:
            error = playbook_result["error"]
            if "AnsibleUndefinedVariable" in error:
                # Extract the undefined variable name
                import re
                match = re.search(r"'([^']+)' is undefined", error)
                if match:
                    var_name = match.group(1)
                    issues["playbook"]["undefined_vars"].append(var_name)
            elif "SyntaxError" in error:
                issues["playbook"]["syntax"].append(error)
            else:
                issues["playbook"]["other"].append(error)
        
        return issues
    
    def generate_recommendations(self, issues):
        """Generate recommendations to improve the converter"""
        recommendations = []
        
        # FQCN recommendations
        if issues["lint"]["fqcn"]:
            recommendations.append({
                "issue": "Fully Qualified Collection Names (FQCN) are not being used",
                "recommendation": "Modify the LLM converter to use FQCN for all Ansible modules (e.g., 'ansible.builtin.template' instead of 'template')",
                "examples": issues["lint"]["fqcn"][:3]  # Show up to 3 examples
            })
        
        # Naming conventions
        if issues["lint"]["naming"]:
            recommendations.append({
                "issue": "Handler names do not follow Ansible naming conventions",
                "recommendation": "Ensure handler names start with an uppercase letter (e.g., 'Restart nginx' instead of 'restart nginx')",
                "examples": issues["lint"]["naming"][:3]
            })
        
        # Truthy values
        if issues["lint"]["truthy"]:
            recommendations.append({
                "issue": "Boolean values are not using the correct format",
                "recommendation": "Use 'true' and 'false' instead of 'yes' and 'no' for boolean values",
                "examples": issues["lint"]["truthy"][:3]
            })
        
        # Undefined variables
        if issues["playbook"]["undefined_vars"]:
            recommendations.append({
                "issue": "Undefined variables in templates",
                "recommendation": "Ensure all variables used in templates are defined in defaults/main.yml",
                "examples": [f"Variable '{var}' is undefined" for var in issues["playbook"]["undefined_vars"][:3]]
            })
        
        return recommendations
    
    def run_test(self):
        """Run the full test"""
        self.log("\n=== Starting Conversion Quality Test ===\n")
        
        # Clone the Chef example
        example_dir = self.clone_chef_example()
        
        # Convert Chef to Ansible
        cookbook_results = self.convert_chef_to_ansible(example_dir)
        
        if not cookbook_results:
            self.log("No cookbooks were converted. Test failed.")
            return False
        
        # Test results
        test_results = []
        
        # Validate each converted cookbook
        for cookbook in cookbook_results:
            self.log(f"\n=== Validating {cookbook['name']} ===\n")
            
            role_path = cookbook["path"]
            
            # Run ansible-lint
            lint_result = self.run_ansible_lint(role_path)
            self.log(f"Lint check: {'✅ Passed' if lint_result['success'] else '❌ Failed'}")
            if not lint_result["success"]:
                self.log("Lint issues:")
                for issue in lint_result["issues"]:
                    self.log(f"  - {issue}")
            
            # Run ansible-playbook --check
            playbook_result = self.run_ansible_playbook_check(role_path)
            self.log(f"Playbook check: {'✅ Passed' if playbook_result['success'] else '❌ Failed'}")
            if not playbook_result["success"]:
                self.log("Playbook issues:")
                self.log(f"  - {playbook_result['error']}")
            
            # Analyze issues
            issues = self.analyze_conversion_issues(lint_result, playbook_result)
            
            # Generate recommendations
            recommendations = self.generate_recommendations(issues)
            
            test_results.append({
                "cookbook": cookbook["name"],
                "lint_result": lint_result,
                "playbook_result": playbook_result,
                "issues": issues,
                "recommendations": recommendations
            })
        
        # Generate report
        self.generate_report(test_results)
        
        # Return overall success
        return all(
            result["lint_result"]["success"] and result["playbook_result"]["success"]
            for result in test_results
        )
    
    def generate_report(self, test_results):
        """Generate a detailed report"""
        self.log("\n=== Conversion Quality Report ===\n")
        
        # Overall statistics
        total_cookbooks = len(test_results)
        lint_passed = sum(1 for result in test_results if result["lint_result"]["success"])
        playbook_passed = sum(1 for result in test_results if result["playbook_result"]["success"])
        
        self.log(f"Total cookbooks tested: {total_cookbooks}")
        self.log(f"Lint checks passed: {lint_passed}/{total_cookbooks}")
        self.log(f"Playbook checks passed: {playbook_passed}/{total_cookbooks}")
        
        # Detailed results
        for result in test_results:
            self.log(f"\nCookbook: {result['cookbook']}")
            self.log(f"Lint check: {'✅ Passed' if result['lint_result']['success'] else '❌ Failed'}")
            self.log(f"Playbook check: {'✅ Passed' if result['playbook_result']['success'] else '❌ Failed'}")
            
            if result["recommendations"]:
                self.log("\nRecommendations to improve the converter:")
                for i, rec in enumerate(result["recommendations"]):
                    self.log(f"  {i+1}. Issue: {rec['issue']}")
                    self.log(f"     Recommendation: {rec['recommendation']}")
                    if rec["examples"]:
                        self.log(f"     Examples:")
                        for ex in rec["examples"]:
                            self.log(f"       - {ex}")
        
        # Save report to file
        report_path = self.test_output_dir / "conversion_quality_report.json"
        with open(report_path, "w") as f:
            json.dump(test_results, f, indent=2)
        
        self.log(f"\nDetailed report saved to {report_path}")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Chef to Ansible conversion quality")
    parser.add_argument("--api-key", help="Anthropic API key")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    # Get API key from environment if not provided
    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    
    if not api_key:
        print("Error: Anthropic API key is required. Set it with --api-key or ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)
    
    # Run test
    tester = ConversionQualityTester(api_key=api_key, verbose=args.verbose)
    success = tester.run_test()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
