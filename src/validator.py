"""
Enhanced Ansible validator with comprehensive validation strategy
"""
import os
import subprocess
import tempfile
import shutil
import yaml
from pathlib import Path

class AnsibleValidator:
    """
    Comprehensive validator for Ansible roles with:
    - Static analysis
    - Dynamic testing
    - Reporting
    """
    
    def __init__(self, verbose=True):
        self.verbose = verbose
        self.results = {
            'errors': [],
            'warnings': [],
            'passed': []
        }
    
    def validate(self, role_path):
        """Validate an Ansible role
        
        This method is called by the converter after generating the role files.
        It performs comprehensive validation on the generated Ansible role.
        
        Args:
            role_path (str or Path): Path to the generated Ansible role
            
        Returns:
            dict: Dictionary with validation results
                - valid (bool): True if validation passes, False otherwise
                - messages (list): List of validation messages
        """
        # Convert path to string if it's a Path object
        if not isinstance(role_path, str):
            role_path = str(role_path)
            
        # Reset results for this validation run
        self.results = {'errors': [], 'warnings': [], 'passed': []}
        
        # Run all validation checks
        try:
            # Structural validation
            self._validate_role_structure(role_path)
            
            # Syntax validation
            self._validate_syntax(role_path)
            
            # Linting
            self._validate_linting(role_path)
            
            # Custom checks
            self._validate_variable_naming(role_path)
            self._validate_template_usage(role_path)
            
            # Dynamic testing (optional based on environment)
            self._test_role_execution(role_path)
        except Exception as e:
            self.results['errors'].append(f"Validation error: {str(e)}")
        
        # Generate report
        self._generate_report()
        
        # Return validation results
        return {
            'valid': len(self.results['errors']) == 0,
            'messages': self.results['errors'] + self.results['warnings']
        }
    
    def _validate_role_structure(self, role_path):
        """Validate role directory structure"""
        required_dirs = ['tasks', 'handlers', 'templates']
        required_files = ['tasks/main.yml', 'meta/main.yml']
        
        for dir in required_dirs:
            path = os.path.join(role_path, dir)
            if not os.path.exists(path):
                self.results['warnings'].append(f"Missing directory: {dir}")
        
        for file in required_files:
            path = os.path.join(role_path, file)
            if not os.path.exists(path):
                self.results['errors'].append(f"Missing required file: {file}")
            else:
                self.results['passed'].append(f"Found required file: {file}")
    
    def _validate_syntax(self, role_path):
        """Validate YAML syntax"""
        try:
            # Check all YAML files
            for root, _, files in os.walk(role_path):
                for file in files:
                    if file.endswith('.yml') or file.endswith('.yaml'):
                        path = os.path.join(root, file)
                        with open(path, 'r') as f:
                            yaml.safe_load(f)
                        self.results['passed'].append(f"Valid YAML: {path}")
        except yaml.YAMLError as e:
            self.results['errors'].append(f"Invalid YAML in {path}: {str(e)}")
    
    def _validate_linting(self, role_path):
        """Run ansible-lint"""
        try:
            result = subprocess.run(
                ['ansible-lint', role_path],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.results['passed'].append("ansible-lint passed")
            else:
                self.results['warnings'].append(
                    f"ansible-lint issues:\n{result.stdout}"
                )
        except Exception as e:
            self.results['errors'].append(f"Linting failed: {str(e)}")
    
    def _validate_variable_naming(self, role_path):
        """Check variable naming conventions"""
        # Implementation would check for consistent naming
        pass
    
    def _validate_template_usage(self, role_path):
        """Verify templates are properly used"""
        # Implementation would check template references
        pass
    
    def _test_role_execution(self, role_path):
        """Test role execution in check mode"""
        try:
            test_dir = tempfile.mkdtemp()
            abs_role_path = os.path.abspath(role_path)
            role_name = os.path.basename(abs_role_path)
            
            # Set up test environment
            roles_dir = os.path.join(test_dir, 'roles')
            os.makedirs(roles_dir)
            
            # Ensure the source path for symlink is absolute
            os.symlink(
                abs_role_path,
                os.path.join(roles_dir, role_name)
            )
            
            # Create minimal inventory
            with open(os.path.join(test_dir, 'inventory'), 'w') as f:
                f.write("localhost ansible_connection=local\n")
            
            # Create test playbook
            playbook = {
                'name': 'Test playbook',
                'hosts': 'localhost',
                'roles': [role_name] # Use the determined role name
            }
            
            with open(os.path.join(test_dir, 'test.yml'), 'w') as f:
                yaml.dump([playbook], f)
            
            # Run in check mode
            result = subprocess.run(
                ['ansible-playbook', '-i', 'inventory', '--check', 'test.yml'],
                cwd=test_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.results['passed'].append("Dry-run execution successful")
            else:
                self.results['errors'].append(
                    f"Dry-run failed:\n{result.stderr}"
                )
            
        except Exception as e:
            self.results['errors'].append(f"Execution test failed: {str(e)}")
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)
    
    def _generate_report(self):
        """Generate validation report"""
        print("\n=== Validation Report ===\n")
        
        if self.verbose:
            for item in self.results['passed']:
                print(f"✅ {item}")
            
            for item in self.results['warnings']:
                print(f"⚠️  {item}")
            
            for item in self.results['errors']:
                print(f"❌ {item}")
        
        print(f"\nSummary: {len(self.results['passed'])} passed, "
              f"{len(self.results['warnings'])} warnings, "
              f"{len(self.results['errors'])} errors")
        
        if self.results['errors']:
            print("\nValidation FAILED")
        else:
            print("\nValidation PASSED")
