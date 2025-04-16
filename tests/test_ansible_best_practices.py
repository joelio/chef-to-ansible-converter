"""
Test module for verifying Ansible best practices implementation
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

import sys
import os

# Add the parent directory to the path so we can import the src modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ansible_generator import AnsibleGenerator
from src.llm_converter import LLMConverter
from src.config import Config


class TestAnsibleBestPractices(unittest.TestCase):
    """Test cases for verifying Ansible best practices implementation"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.output_path = Path(self.temp_dir) / "test_role"
        
        # Create a sample ansible_data structure
        self.ansible_data = {
            "name": "test-cookbook",
            "tasks": [
                {
                    "name": "Install nginx",
                    "ansible.builtin.package": {
                        "name": "nginx",
                        "state": "present"
                    }
                },
                {
                    "name": "Configure nginx",
                    "ansible.builtin.template": {
                        "src": "nginx.conf.j2",
                        "dest": "/etc/nginx/nginx.conf"
                    },
                    "notify": "Restart nginx"
                }
            ],
            "handlers": [
                {
                    "name": "Restart nginx",
                    "ansible.builtin.service": {
                        "name": "nginx",
                        "state": "restarted"
                    }
                }
            ],
            "variables": {
                "nginx_dir": "/etc/nginx",
                "nginx_user": "nginx",
                "nginx_port": 80,
                "ansible_distribution": "Ubuntu",
                "_internal_var": "internal value"
            },
            "templates": [
                {
                    "path": "nginx.conf.j2",
                    "content": "# Nginx configuration\nuser {{ nginx_user }};\nworker_processes auto;\n\nhttp {\n    server {\n        listen {{ nginx_port }};\n    }\n}"
                }
            ]
        }
        
        # Initialize the generator
        self.generator = AnsibleGenerator()

    def tearDown(self):
        """Clean up after tests"""
        shutil.rmtree(self.temp_dir)

    def test_role_structure(self):
        """Test that the role structure follows best practices"""
        # Generate the role
        self.generator.generate_ansible_role(self.ansible_data, self.output_path)
        
        # Verify directory structure
        for dir_name in ['tasks', 'handlers', 'templates', 'files', 'vars', 'defaults', 'meta']:
            self.assertTrue(os.path.isdir(self.output_path / dir_name), 
                           f"Directory {dir_name} not created")
        
        # Verify master playbook and inventory
        self.assertTrue(os.path.isfile(self.output_path.parent / "site.yml"), 
                       "Master playbook not created")
        self.assertTrue(os.path.isdir(self.output_path.parent / "inventory"), 
                       "Inventory directory not created")
        self.assertTrue(os.path.isfile(self.output_path.parent / "inventory" / "hosts"), 
                       "Inventory hosts file not created")
        self.assertTrue(os.path.isfile(self.output_path.parent / ".gitignore"), 
                       ".gitignore file not created")

    def test_task_tags(self):
        """Test that tasks have appropriate tags"""
        # Generate the role
        self.generator.generate_ansible_role(self.ansible_data, self.output_path)
        
        # Read the tasks file
        with open(self.output_path / "tasks" / "main.yml", "r") as f:
            tasks = yaml.safe_load(f)
        
        # Verify tags
        for task in tasks:
            self.assertIn("tags", task, f"Task '{task['name']}' does not have tags")
            self.assertIn("test_cookbook", task["tags"], 
                         f"Task '{task['name']}' does not have role name tag")
            
            # Check for specific tags based on task type
            if "package" in task["name"].lower():
                self.assertIn("packages", task["tags"], 
                             f"Package task '{task['name']}' does not have 'packages' tag")
            if "nginx" in task["name"].lower() and "configure" in task["name"].lower():
                self.assertIn("config", task["tags"], 
                             f"Config task '{task['name']}' does not have 'config' tag")

    def test_handler_error_handling(self):
        """Test that handlers have proper error handling"""
        # Generate the role
        self.generator.generate_ansible_role(self.ansible_data, self.output_path)
        
        # Read the handlers file
        with open(self.output_path / "handlers" / "main.yml", "r") as f:
            handlers = yaml.safe_load(f)
        
        # Verify error handling in service handlers
        for handler in handlers:
            if "service" in handler:
                self.assertIn("ignore_errors", handler, 
                             f"Service handler '{handler['name']}' does not have ignore_errors")
                self.assertIn("register", handler, 
                             f"Service handler '{handler['name']}' does not register result")
                self.assertIn("failed_when", handler, 
                             f"Service handler '{handler['name']}' does not have failed_when")

    def test_variable_separation(self):
        """Test that variables are properly separated between defaults and vars"""
        # Generate the role
        self.generator.generate_ansible_role(self.ansible_data, self.output_path)
        
        # Read the defaults file
        with open(self.output_path / "defaults" / "main.yml", "r") as f:
            defaults = yaml.safe_load(f)
        
        # Read the vars file
        with open(self.output_path / "vars" / "main.yml", "r") as f:
            vars_data = yaml.safe_load(f)
        
        # Verify variable separation
        self.assertIn("nginx_dir", defaults, "User-configurable variable not in defaults")
        self.assertIn("nginx_port", defaults, "User-configurable variable not in defaults")
        self.assertIn("_internal_var", vars_data, "Internal variable not in vars")
        self.assertIn("ansible_distribution", vars_data, "System variable not in vars")

    def test_readme_content(self):
        """Test that README.md contains comprehensive documentation"""
        # Generate the role
        self.generator.generate_ansible_role(self.ansible_data, self.output_path)
        
        # Read the README file
        with open(self.output_path / "README.md", "r") as f:
            readme_content = f.read()
        
        # Verify README content
        self.assertIn("# test-cookbook", readme_content, "README does not have title")
        self.assertIn("## Requirements", readme_content, "README does not have requirements section")
        self.assertIn("## Role Variables", readme_content, "README does not have variables section")
        self.assertIn("### Default Variables", readme_content, "README does not have default variables section")
        self.assertIn("### Internal Variables", readme_content, "README does not have internal variables section")
        self.assertIn("## Example Playbook", readme_content, "README does not have example playbook section")
        self.assertIn("## Usage with Tags", readme_content, "README does not have tags usage section")
        self.assertIn("## Conversion Notes", readme_content, "README does not have conversion notes section")


if __name__ == "__main__":
    unittest.main()
