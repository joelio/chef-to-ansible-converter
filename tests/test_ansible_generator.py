#!/usr/bin/env python3
"""
Unit tests for the AnsibleGenerator module
"""
import os
import sys
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ansible_generator import AnsibleGenerator


class TestAnsibleGenerator:
    """Test cases for the AnsibleGenerator class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.generator = AnsibleGenerator()

    def test_initialization(self):
        """Test generator initialization"""
        generator = AnsibleGenerator()
        assert hasattr(generator, 'yaml')
        assert generator.yaml is not None

    @patch('pathlib.Path.mkdir')
    def test_generate_ansible_role(self, mock_mkdir):
        """Test generating Ansible role structure"""
        # Mock the _write_yaml_file method
        with patch.object(self.generator, '_write_yaml_file') as mock_write_yaml:
            # Mock open for meta file
            with patch('builtins.open', mock_open()):
                # Create test data
                ansible_data = {
                    'name': 'test_role',
                    'tasks': [{'name': 'Install nginx', 'apt': {'name': 'nginx'}}],
                    'handlers': [{'name': 'Restart nginx', 'service': {'name': 'nginx', 'state': 'restarted'}}],
                    'variables': {'nginx_port': 80},
                    'templates': []
                }
                
                # Call the method
                self.generator.generate_ansible_role(ansible_data, "output/test_role")
                
                # Verify directories were created
                assert mock_mkdir.call_count >= 1
                
                # Verify YAML files were written
                assert mock_write_yaml.call_count >= 3  # tasks, handlers, variables

    @patch('builtins.open', new_callable=mock_open)
    def test_write_yaml_file(self, mock_file):
        """Test writing YAML file"""
        # Create test data
        data = [{'name': 'Install nginx', 'apt': {'name': 'nginx'}}]
        
        # Call the method
        with patch.object(self.generator.yaml, 'dump') as mock_dump:
            self.generator._write_yaml_file("output/test_role/tasks/main.yml", data)
            
            # Verify file was opened
            mock_file.assert_called_with("output/test_role/tasks/main.yml", "w")
            
            # Verify YAML dump was called
            mock_dump.assert_called_once()

    def test_process_templates(self):
        """Test processing templates"""
        # Mock Path.mkdir and open
        with patch('pathlib.Path.mkdir'):
            with patch('builtins.open', mock_open()):
                with patch('pathlib.Path.parent', new_callable=MagicMock):
                    with patch('pathlib.Path.touch'):
                        # Create test data
                        role_path = Path("output/test_role")
                        templates = [
                            {
                                'name': 'nginx.conf',
                                'path': 'nginx.conf.j2',
                                'content': 'server { listen {{ port }}; }'
                            }
                        ]
                        
                        # Create ansible_data with templates
                        ansible_data = {
                            'name': 'test_role',
                            'tasks': [],
                            'handlers': [],
                            'variables': {},
                            'templates': templates
                        }
                        
                        # Call the generate_ansible_role method which processes templates
                        self.generator.generate_ansible_role(ansible_data, role_path)
                        
                        # No assertions needed - we're just checking it doesn't raise exceptions

    @patch('builtins.open', new_callable=mock_open)
    def test_write_yaml_file(self, mock_file):
        """Test writing YAML file"""
        # Create test data
        data = [{'name': 'Install nginx', 'apt': {'name': 'nginx'}}]
        file_path = Path("output/test_role/tasks/main.yml")
        
        # Call the method
        with patch.object(self.generator.yaml, 'dump') as mock_dump:
            self.generator._write_yaml_file(file_path, data)
            
            # Verify file was opened
            mock_file.assert_called_once_with(file_path, 'w')
            
            # Verify YAML dump was called
            mock_dump.assert_called_once()

    @patch('builtins.open', new_callable=mock_open)
    def test_meta_file_creation(self, mock_file):
        """Test creating meta file"""
        # Mock mkdir
        with patch('pathlib.Path.mkdir'):
            # Call the method
            role_path = Path("output/test_role")
            ansible_data = {
                'name': 'test_cookbook',
                'tasks': [],
                'handlers': [],
                'variables': {}
            }
            
            with patch.object(self.generator, '_write_yaml_file') as mock_write_yaml:
                self.generator.generate_ansible_role(ansible_data, role_path)
                
                # Verify _write_yaml_file was called for meta file
                meta_file_call = False
                for call in mock_write_yaml.call_args_list:
                    if str(call[0][0]).endswith('meta/main.yml'):
                        meta_file_call = True
                        break
                
                assert meta_file_call, "Meta file was not created"

    @patch('builtins.open', new_callable=mock_open)
    def test_readme_file_creation(self, mock_file):
        """Test creating README file"""
        # Mock mkdir
        with patch('pathlib.Path.mkdir'):
            # Call the method
            role_path = Path("output/test_role")
            ansible_data = {
                'name': 'test_cookbook',
                'tasks': [],
                'handlers': [],
                'variables': {}
            }
            
            with patch.object(self.generator, '_write_yaml_file'):
                self.generator.generate_ansible_role(ansible_data, role_path)
                
                # Verify README file was opened
                readme_file_call = False
                for call in mock_file.call_args_list:
                    if str(call[0][0]).endswith('README.md'):
                        readme_file_call = True
                        break
                
                assert readme_file_call, "README file was not created"
                
                # Verify content was written
                handle = mock_file()
                assert handle.write.call_count >= 1
