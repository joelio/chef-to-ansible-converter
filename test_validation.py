#!/usr/bin/env python3
"""
Test Validation Script for Chef to Ansible Converter

This script focuses specifically on validating converted Ansible playbooks:
1. Runs ansible-lint on converted playbooks
2. Performs ansible-playbook --check (dry run) validation
3. Generates detailed validation reports
"""

import os
import sys
import json
import yaml
import argparse
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

class AnsibleValidator:
    """Enhanced validator for Ansible playbooks and roles"""
    
    def __init__(self, verbose=True):
        self.verbose = verbose
    
    def log(self, message):
        """Log a message if verbose is enabled"""
        if self.verbose:
            print(message)
    
    def validate_yaml(self, file_path):
        """Validate YAML syntax"""
        try:
            with open(file_path, 'r') as f:
                yaml.safe_load(f)
            return {"success": True, "message": "Valid YAML"}
        except yaml.YAMLError as e:
            return {"success": False, "message": str(e)}
    
    def run_ansible_lint(self, target_path):
        """Run ansible-lint on the target path"""
        self.log(f"Running ansible-lint on {target_path}")
        
        try:
            result = subprocess.run(
                ["ansible-lint", str(target_path), "--parseable"],
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
    
    def run_ansible_playbook_check(self, playbook_path, inventory_path=None):
        """Run ansible-playbook --check on the playbook"""
        self.log(f"Running ansible-playbook --check on {playbook_path}")
        
        try:
            cmd = ["ansible-playbook", "--check"]
            
            if inventory_path:
                cmd.extend(["-i", str(inventory_path)])
            else:
                # Create a minimal inventory if none provided
                with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_inventory:
                    temp_inventory.write("localhost ansible_connection=local\n")
                    inventory_path = temp_inventory.name
                cmd.extend(["-i", inventory_path])
            
            cmd.append(str(playbook_path))
            
            result = subprocess.run(
                cmd,
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
        finally:
            # Clean up temporary inventory if we created one
            if not inventory_path and os.path.exists(temp_inventory.name):
                os.unlink(temp_inventory.name)
    
    def validate_role(self, role_path):
        """Validate an Ansible role"""
        self.log(f"\n=== Validating Role: {role_path} ===\n")
        
        results = {
            "role_path": str(role_path),
            "structure": self._validate_role_structure(role_path),
            "yaml": self._validate_role_yaml(role_path),
            "lint": self.run_ansible_lint(role_path),
            "dry_run": self._test_role_execution(role_path)
        }
        
        # Determine overall success
        results["success"] = (
            results["structure"]["success"] and
            results["yaml"]["success"] and
            results["lint"]["success"] and
            results["dry_run"]["success"]
        )
        
        return results
    
    def validate_playbook(self, playbook_path, inventory_path=None):
        """Validate an Ansible playbook"""
        self.log(f"\n=== Validating Playbook: {playbook_path} ===\n")
        
        results = {
            "playbook_path": str(playbook_path),
            "yaml": self.validate_yaml(playbook_path),
            "lint": self.run_ansible_lint(playbook_path),
            "dry_run": self.run_ansible_playbook_check(playbook_path, inventory_path)
        }
        
        # Determine overall success
        results["success"] = (
            results["yaml"]["success"] and
            results["lint"]["success"] and
            results["dry_run"]["success"]
        )
        
        return results
    
    def _validate_role_structure(self, role_path):
        """Validate role directory structure"""
        role_path = Path(role_path)
        
        # Define expected directories and files
        expected_dirs = ["tasks", "defaults", "handlers", "meta", "templates", "vars"]
        required_files = ["tasks/main.yml", "meta/main.yml"]
        
        # Check directories
        missing_dirs = []
        for dir_name in expected_dirs:
            if not (role_path / dir_name).exists():
                missing_dirs.append(dir_name)
        
        # Check required files
        missing_files = []
        for file_path in required_files:
            if not (role_path / file_path).exists():
                missing_files.append(file_path)
        
        success = len(missing_files) == 0  # Only fail if required files are missing
        
        return {
            "success": success,
            "missing_dirs": missing_dirs,
            "missing_files": missing_files
        }
    
    def _validate_role_yaml(self, role_path):
        """Validate YAML syntax for all YAML files in the role"""
        role_path = Path(role_path)
        
        yaml_files = list(role_path.glob("**/*.yml")) + list(role_path.glob("**/*.yaml"))
        
        results = {
            "success": True,
            "files": []
        }
        
        for file_path in yaml_files:
            file_result = self.validate_yaml(file_path)
            results["files"].append({
                "path": str(file_path.relative_to(role_path)),
                "success": file_result["success"],
                "message": file_result["message"]
            })
            
            if not file_result["success"]:
                results["success"] = False
        
        return results
    
    def _test_role_execution(self, role_path):
        """Test role execution in check mode"""
        role_path = Path(role_path)
        role_name = role_path.name
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                
                # Create roles directory and symlink the role
                roles_dir = temp_dir_path / "roles"
                roles_dir.mkdir()
                
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
                
                playbook_path = temp_dir_path / "test_playbook.yml"
                with open(playbook_path, "w") as f:
                    yaml.dump([test_playbook], f)
                
                # Run ansible-playbook in check mode
                return self.run_ansible_playbook_check(playbook_path, temp_dir_path / "inventory")
        
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e)
            }

def validate_directory(directory_path, validator, output_file=None):
    """Validate all Ansible roles and playbooks in a directory"""
    directory_path = Path(directory_path)
    
    # Find all potential role directories (containing tasks/main.yml)
    role_paths = []
    for tasks_main in directory_path.glob("**/tasks/main.yml"):
        role_path = tasks_main.parent.parent
        role_paths.append(role_path)
    
    # Find all playbook files (YAML files in the root or playbooks directory)
    playbook_paths = []
    for yaml_file in list(directory_path.glob("*.yml")) + list(directory_path.glob("*.yaml")):
        # Simple heuristic: if it contains "hosts:" it's probably a playbook
        with open(yaml_file, 'r') as f:
            content = f.read()
            if "hosts:" in content:
                playbook_paths.append(yaml_file)
    
    # Also check playbooks directory if it exists
    playbooks_dir = directory_path / "playbooks"
    if playbooks_dir.exists():
        for yaml_file in list(playbooks_dir.glob("*.yml")) + list(playbooks_dir.glob("*.yaml")):
            with open(yaml_file, 'r') as f:
                content = f.read()
                if "hosts:" in content:
                    playbook_paths.append(yaml_file)
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "directory": str(directory_path),
        "roles": [],
        "playbooks": [],
        "success": True
    }
    
    # Validate roles
    for role_path in role_paths:
        role_result = validator.validate_role(role_path)
        results["roles"].append(role_result)
        if not role_result["success"]:
            results["success"] = False
    
    # Validate playbooks
    for playbook_path in playbook_paths:
        playbook_result = validator.validate_playbook(playbook_path)
        results["playbooks"].append(playbook_result)
        if not playbook_result["success"]:
            results["success"] = False
    
    # Save results to file if requested
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
    
    return results

def print_validation_summary(results):
    """Print a summary of validation results"""
    print("\n=== Validation Summary ===\n")
    
    print(f"Directory: {results['directory']}")
    print(f"Timestamp: {results['timestamp']}")
    print(f"Overall Status: {'✅ Success' if results['success'] else '❌ Failed'}")
    
    print(f"\nRoles: {len(results['roles'])}")
    for i, role in enumerate(results['roles']):
        role_path = Path(role['role_path']).name
        print(f"  {i+1}. {role_path}: {'✅ Success' if role['success'] else '❌ Failed'}")
        
        if not role['structure']['success']:
            print(f"     - Missing required files: {', '.join(role['structure']['missing_files'])}")
        
        if not role['yaml']['success']:
            failed_files = [f['path'] for f in role['yaml']['files'] if not f['success']]
            print(f"     - YAML validation failed for: {', '.join(failed_files)}")
        
        if not role['lint']['success']:
            print(f"     - Linting issues: {len(role['lint']['issues'])}")
        
        if not role['dry_run']['success']:
            print(f"     - Dry run failed: {role['dry_run']['error']}")
    
    print(f"\nPlaybooks: {len(results['playbooks'])}")
    for i, playbook in enumerate(results['playbooks']):
        playbook_path = Path(playbook['playbook_path']).name
        print(f"  {i+1}. {playbook_path}: {'✅ Success' if playbook['success'] else '❌ Failed'}")
        
        if not playbook['yaml']['success']:
            print(f"     - YAML validation failed: {playbook['yaml']['message']}")
        
        if not playbook['lint']['success']:
            print(f"     - Linting issues: {len(playbook['lint']['issues'])}")
        
        if not playbook['dry_run']['success']:
            print(f"     - Dry run failed: {playbook['dry_run']['error']}")

def main():
    """Main entry point for the validation script"""
    parser = argparse.ArgumentParser(description="Validate Ansible roles and playbooks")
    parser.add_argument("directory", help="Directory containing Ansible roles and playbooks to validate")
    parser.add_argument("--output", help="Output file for validation results (JSON)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    validator = AnsibleValidator(verbose=args.verbose)
    results = validate_directory(args.directory, validator, args.output)
    
    print_validation_summary(results)
    
    # Return exit code based on validation success
    return 0 if results["success"] else 1

if __name__ == "__main__":
    sys.exit(main())
