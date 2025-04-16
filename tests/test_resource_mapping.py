"""
Tests for the resource mapping module.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from src.resource_mapping import ResourceMapping


class TestResourceMapping(unittest.TestCase):
    """Test cases for the ResourceMapping class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary mapping file for testing
        self.temp_mapping_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_mapping_path = self.temp_mapping_file.name
        
        # Sample custom mappings for testing
        self.test_mappings = {
            "test_resource": {
                "ansible_module": "test.module",
                "property_mapping": {
                    "test_prop": "module_param",
                    "bool_prop": "bool_param",
                    "value_mapping": {
                        "bool_prop": {"true": "present", "false": "absent"}
                    }
                }
            },
            "another_resource": {
                "ansible_module": "another.module",
                "property_mapping": {
                    "name": "module_name",
                    "action": "state",
                    "value_mapping": {
                        "action": {"start": "started", "stop": "stopped"}
                    }
                }
            }
        }
        
        # Write the test mappings to the temporary file
        with open(self.temp_mapping_path, 'w') as f:
            json.dump(self.test_mappings, f)
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Remove the temporary mapping file
        if os.path.exists(self.temp_mapping_path):
            os.unlink(self.temp_mapping_path)
    
    def test_load_default_mappings(self):
        """Test loading default mappings."""
        mapper = ResourceMapping()
        
        # Check that default mappings are loaded
        self.assertIn("mysql_database", mapper.mappings)
        self.assertIn("postgresql_database", mapper.mappings)
        self.assertIn("apache2_site", mapper.mappings)
        
        # Check a specific mapping
        mysql_mapping = mapper.mappings.get("mysql_database")
        self.assertEqual(mysql_mapping["ansible_module"], "community.mysql.mysql_db")
        self.assertEqual(mysql_mapping["property_mapping"]["database_name"], "name")
    
    def test_load_custom_mappings(self):
        """Test loading custom mappings from a file."""
        mapper = ResourceMapping(self.temp_mapping_path)
        
        # Check that custom mappings are loaded
        self.assertIn("test_resource", mapper.mappings)
        self.assertIn("another_resource", mapper.mappings)
        
        # Check a specific custom mapping
        test_mapping = mapper.mappings.get("test_resource")
        self.assertEqual(test_mapping["ansible_module"], "test.module")
        self.assertEqual(test_mapping["property_mapping"]["test_prop"], "module_param")
    
    def test_get_mapping(self):
        """Test getting a mapping for a resource type."""
        mapper = ResourceMapping(self.temp_mapping_path)
        
        # Get an existing mapping
        mapping = mapper.get_mapping("test_resource")
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping["ansible_module"], "test.module")
        
        # Get a non-existent mapping
        mapping = mapper.get_mapping("non_existent_resource")
        self.assertIsNone(mapping)
    
    def test_transform_resource_with_mapping(self):
        """Test transforming a resource with an existing mapping."""
        mapper = ResourceMapping(self.temp_mapping_path)
        
        # Resource data to transform
        resource_data = {
            "test_prop": "test_value",
            "bool_prop": "true"
        }
        
        # Transform the resource
        tasks = mapper.transform_resource("test_resource", resource_data)
        
        # Check the transformed tasks
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        
        self.assertEqual(task["name"], "Converted from Chef custom resource 'test_resource'")
        self.assertIn("test.module", task)
        self.assertEqual(task["test.module"]["module_param"], "test_value")
        self.assertEqual(task["test.module"]["bool_param"], "present")  # Value mapping applied
    
    def test_transform_resource_without_mapping(self):
        """Test transforming a resource without an existing mapping."""
        mapper = ResourceMapping(self.temp_mapping_path)
        
        # Resource data to transform
        resource_data = {
            "some_prop": "some_value"
        }
        
        # Transform the resource
        tasks = mapper.transform_resource("unknown_resource", resource_data)
        
        # Check the placeholder task
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        
        self.assertIn("TODO: Convert Chef custom resource 'unknown_resource'", task["name"])
        self.assertIn("ansible.builtin.debug", task)
        self.assertIn("Chef custom resource 'unknown_resource' requires manual conversion", 
                     task["ansible.builtin.debug"]["msg"])
    
    def test_custom_handler(self):
        """Test registering and applying a custom handler."""
        mapper = ResourceMapping(self.temp_mapping_path)
        
        # Define a custom handler function
        def custom_handler(resource_data):
            return [{
                "name": "Custom handled resource",
                "custom.module": {
                    "param1": resource_data.get("prop1", "default"),
                    "param2": resource_data.get("prop2", "default")
                }
            }]
        
        # Register the custom handler
        mapper.register_custom_handler("custom_resource", custom_handler)
        
        # Check that the handler was registered
        self.assertTrue(mapper.has_custom_handler("custom_resource"))
        
        # Resource data to transform
        resource_data = {
            "prop1": "value1",
            "prop2": "value2"
        }
        
        # Transform the resource using the custom handler
        tasks = mapper.transform_resource("custom_resource", resource_data)
        
        # Check the transformed tasks
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        
        self.assertEqual(task["name"], "Custom handled resource")
        self.assertIn("custom.module", task)
        self.assertEqual(task["custom.module"]["param1"], "value1")
        self.assertEqual(task["custom.module"]["param2"], "value2")


if __name__ == '__main__':
    unittest.main()
