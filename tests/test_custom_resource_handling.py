"""
Tests for the custom resource handling in the LLM converter.
"""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.config import Config
from src.llm_converter import LLMConverter


class TestCustomResourceHandling(unittest.TestCase):
    """Test cases for custom resource handling in the LLM converter."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock config
        self.config = Config(api_key="test_key")
        
        # Create a temporary mapping file for testing
        self.temp_mapping_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_mapping_path = self.temp_mapping_file.name
        
        # Sample custom mappings for testing
        self.test_mappings = {
            "mysql_database": {
                "ansible_module": "community.mysql.mysql_db",
                "property_mapping": {
                    "database_name": "name",
                    "connection": "login_host",
                    "user": "login_user",
                    "password": "login_password"
                }
            }
        }
        
        # Write the test mappings to the temporary file
        with open(self.temp_mapping_path, 'w') as f:
            json.dump(self.test_mappings, f)
        
        # Set the resource mapping path in the config
        self.config.resource_mapping_path = self.temp_mapping_path
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Remove the temporary mapping file
        if os.path.exists(self.temp_mapping_path):
            os.unlink(self.temp_mapping_path)
    
    @patch('anthropic.Anthropic')
    def test_is_custom_resource_placeholder(self, mock_anthropic):
        """Test detection of custom resource placeholders."""
        # Mock the Anthropic client
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        
        # Create a converter instance
        converter = LLMConverter(self.config)
        
        # Test cases for custom resource placeholders
        test_cases = [
            # Task with custom resource in name
            {
                "task": {
                    "name": "TODO: Convert Chef custom resource 'mysql_database'",
                    "ansible.builtin.debug": {
                        "msg": "Chef custom resource 'mysql_database' requires manual conversion"
                    }
                },
                "expected": True
            },
            # Task with custom resource in debug message
            {
                "task": {
                    "name": "Some task",
                    "ansible.builtin.debug": {
                        "msg": "Chef custom resource 'mysql_database' requires manual conversion"
                    }
                },
                "expected": True
            },
            # Regular task (not a custom resource)
            {
                "task": {
                    "name": "Install package",
                    "ansible.builtin.package": {
                        "name": "nginx",
                        "state": "present"
                    }
                },
                "expected": False
            }
        ]
        
        # Run the test cases
        for case in test_cases:
            result = converter._is_custom_resource_placeholder(case["task"])
            self.assertEqual(result, case["expected"])
    
    @patch('anthropic.Anthropic')
    def test_extract_resource_type(self, mock_anthropic):
        """Test extraction of resource type from placeholders."""
        # Mock the Anthropic client
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        
        # Create a converter instance
        converter = LLMConverter(self.config)
        
        # Test cases for resource type extraction
        test_cases = [
            # Task with resource type in name
            {
                "task": {
                    "name": "TODO: Convert Chef custom resource 'mysql_database'",
                    "ansible.builtin.debug": {
                        "msg": "Chef custom resource 'mysql_database' requires manual conversion"
                    }
                },
                "expected": "mysql_database"
            },
            # Task with resource type in debug message
            {
                "task": {
                    "name": "Some task",
                    "ansible.builtin.debug": {
                        "msg": "Chef custom resource 'postgresql_database' requires manual conversion"
                    }
                },
                "expected": "postgresql_database"
            },
            # Task with no clear resource type
            {
                "task": {
                    "name": "Some other task",
                    "ansible.builtin.debug": {
                        "msg": "Some message"
                    }
                },
                "expected": "custom_resource"
            }
        ]
        
        # Run the test cases
        for case in test_cases:
            result = converter._extract_resource_type(case["task"])
            self.assertEqual(result, case["expected"])
    
    @patch('anthropic.Anthropic')
    def test_extract_resource_data(self, mock_anthropic):
        """Test extraction of resource data from placeholders."""
        # Mock the Anthropic client
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        
        # Create a converter instance
        converter = LLMConverter(self.config)
        
        # Test case for resource data extraction
        task = {
            "name": "TODO: Convert Chef custom resource 'mysql_database'",
            "ansible.builtin.debug": {
                "msg": "Chef custom resource 'mysql_database' requires manual conversion"
            },
            "vars": {
                "database_name": "mydb",
                "connection": "localhost",
                "user": "dbuser",
                "password": "dbpass"
            }
        }
        
        # Extract resource data
        result = converter._extract_resource_data(task)
        
        # Check the extracted data
        self.assertEqual(result["database_name"], "mydb")
        self.assertEqual(result["connection"], "localhost")
        self.assertEqual(result["user"], "dbuser")
        self.assertEqual(result["password"], "dbpass")
    
    @patch('anthropic.Anthropic')
    def test_post_process_custom_resources(self, mock_anthropic):
        """Test post-processing of custom resources."""
        # Mock the Anthropic client
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        
        # Create a converter instance
        converter = LLMConverter(self.config)
        
        # Sample conversion result with a custom resource placeholder
        result = {
            "tasks": [
                {
                    "name": "Install package",
                    "ansible.builtin.package": {
                        "name": "nginx",
                        "state": "present"
                    }
                },
                {
                    "name": "TODO: Convert Chef custom resource 'mysql_database'",
                    "ansible.builtin.debug": {
                        "msg": "Chef custom resource 'mysql_database' requires manual conversion"
                    },
                    "vars": {
                        "database_name": "mydb",
                        "connection": "localhost",
                        "user": "dbuser",
                        "password": "dbpass"
                    }
                }
            ],
            "handlers": [],
            "variables": {}
        }
        
        # Post-process the result
        processed_result = converter._post_process_custom_resources(result)
        
        # Check that the regular task is unchanged
        self.assertEqual(processed_result["tasks"][0]["name"], "Install package")
        
        # Check that the custom resource was transformed
        self.assertEqual(len(processed_result["tasks"]), 2)
        transformed_task = processed_result["tasks"][1]
        
        # The transformed task should use the mysql_db module
        self.assertIn("community.mysql.mysql_db", transformed_task)
        self.assertEqual(transformed_task["community.mysql.mysql_db"]["name"], "mydb")
        self.assertEqual(transformed_task["community.mysql.mysql_db"]["login_host"], "localhost")
        self.assertEqual(transformed_task["community.mysql.mysql_db"]["login_user"], "dbuser")
        self.assertEqual(transformed_task["community.mysql.mysql_db"]["login_password"], "dbpass")
    
    @patch('anthropic.Anthropic')
    def test_handle_unknown_custom_resource(self, mock_anthropic):
        """Test handling of unknown custom resources."""
        # Mock the Anthropic client
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        
        # Create a converter instance
        converter = LLMConverter(self.config)
        
        # Sample conversion result with an unknown custom resource
        result = {
            "tasks": [
                {
                    "name": "TODO: Convert Chef custom resource 'unknown_resource'",
                    "ansible.builtin.debug": {
                        "msg": "Chef custom resource 'unknown_resource' requires manual conversion"
                    },
                    "vars": {
                        "some_prop": "some_value"
                    }
                }
            ],
            "handlers": [],
            "variables": {}
        }
        
        # Post-process the result
        processed_result = converter._post_process_custom_resources(result)
        
        # Check that a placeholder task was created
        self.assertEqual(len(processed_result["tasks"]), 1)
        task = processed_result["tasks"][0]
        
        # The task should still be a placeholder
        self.assertIn("TODO: Convert Chef custom resource 'unknown_resource'", task["name"])
        self.assertIn("ansible.builtin.debug", task)


if __name__ == '__main__':
    unittest.main()
