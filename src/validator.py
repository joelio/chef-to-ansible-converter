"""
Validator module for the Chef to Ansible converter
"""

import os
import subprocess
from pathlib import Path

class AnsibleValidator:
    """Validates generated Ansible code"""
    
    def __init__(self):
        """Initialize the Ansible validator"""
        pass
    
    def validate(self, ansible_path):
        """Validate an Ansible role
        
        Args:
            ansible_path (str or Path): Path to the Ansible role
            
        Returns:
            dict: Validation results
        """
        # Convert string path to Path object if needed
        ansible_path = Path(ansible_path) if isinstance(ansible_path, str) else ansible_path
        
        results = {
            'valid': True,
            'messages': []
        }
        
        # Check if ansible-playbook is available
        if not self._is_ansible_available():
            results['messages'].append("Warning: ansible-playbook not found, skipping syntax validation")
            return results
        
        # Validate syntax
        syntax_result = self.validate_syntax(ansible_path)
        if not syntax_result['valid']:
            results['valid'] = False
            results['messages'].extend(syntax_result['messages'])
        
        # Validate with ansible-lint if available
        lint_result = self.validate_lint(ansible_path)
        if not lint_result['valid']:
            # Linting failures don't make the overall validation fail
            # but we include the messages
            results['messages'].extend(lint_result['messages'])
        
        return results
    
    def _is_ansible_available(self):
        """
        Check if ansible-playbook is available
        
        Returns:
            bool: True if ansible-playbook is available, False otherwise
        """
        try:
            subprocess.run(['ansible-playbook', '--version'], 
                          stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE, 
                          check=False)
            return True
        except FileNotFoundError:
            return False
    
    def validate_syntax(self, ansible_path):
        """Validate Ansible role syntax using ansible-playbook --syntax-check
        
        Args:
            ansible_path (str or Path): Path to the Ansible role
            
        Returns:
            dict: Validation results
        """
        # Convert string path to Path object if needed
        ansible_path = Path(ansible_path) if isinstance(ansible_path, str) else ansible_path
        
        results = {
            'valid': True,
            'messages': []
        }
        
        # Create a temporary playbook to test the role
        temp_playbook = ansible_path / 'test_playbook.yml'
        with open(temp_playbook, 'w') as f:
            f.write(f"""---
- hosts: localhost
  roles:
    - {ansible_path.name}
""")
        
        try:
            # Run ansible-playbook with --syntax-check
            process = subprocess.run(
                ['ansible-playbook', '--syntax-check', str(temp_playbook)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if process.returncode != 0:
                results['valid'] = False
                results['messages'].append(f"Syntax validation failed: {process.stderr}")
        except Exception as e:
            results['valid'] = False
            results['messages'].append(f"Error during syntax validation: {str(e)}")
        finally:
            # Clean up temporary playbook
            if temp_playbook.exists():
                temp_playbook.unlink()
        
        return results
    
    def validate_lint(self, ansible_path):
        """
        Validate Ansible code with ansible-lint
        
        Args:
            ansible_path (str or Path): Path to the generated Ansible role
            
        Returns:
            dict: Validation results
        """
        # Convert string path to Path object if needed
        ansible_path = Path(ansible_path) if isinstance(ansible_path, str) else ansible_path
        results = {
            'valid': True,
            'messages': []
        }
        
        # Check if ansible-lint is available
        try:
            subprocess.run(['ansible-lint', '--version'], 
                          stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE, 
                          check=False)
        except FileNotFoundError:
            results['messages'].append("Warning: ansible-lint not found, skipping linting")
            return results
        
        try:
            # Run ansible-lint
            process = subprocess.run(
                ['ansible-lint', str(ansible_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if process.returncode != 0:
                results['valid'] = False
                # Parse lint output and add to messages
                lint_output = process.stdout or process.stderr
                for line in lint_output.splitlines():
                    if line.strip():
                        results['messages'].append(f"Lint: {line.strip()}")
        except Exception as e:
            results['valid'] = False
            results['messages'].append(f"Error during linting: {str(e)}")
        
        return results
