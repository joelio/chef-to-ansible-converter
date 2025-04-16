"""
Resource Mapping Registry for Chef to Ansible Converter.

This module provides a configurable mapping system for translating Chef custom resources
to Ansible modules, roles, or collections.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

logger = logging.getLogger(__name__)

class ResourceMapping:
    """Maps Chef custom resources to Ansible equivalents."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the resource mapping registry.
        
        Args:
            config_path: Path to a JSON mapping configuration file
        """
        self.mappings = {}
        self.custom_handlers = {}
        
        # Load default mappings
        self._load_default_mappings()
        
        # Load user-defined mappings if provided
        if config_path:
            self._load_custom_mappings(config_path)
    
    def _load_default_mappings(self) -> None:
        """Load the default resource mappings."""
        # Common Chef custom resources and their Ansible equivalents
        self.mappings = {
            # Database resources
            "mysql_database": {
                "ansible_module": "community.mysql.mysql_db",
                "property_mapping": {
                    "database_name": "name",
                    "connection": "login_host",
                    "user": "login_user",
                    "password": "login_password"
                }
            },
            "postgresql_database": {
                "ansible_module": "community.postgresql.postgresql_db",
                "property_mapping": {
                    "database_name": "name",
                    "connection": "login_host",
                    "user": "login_user",
                    "password": "login_password"
                }
            },
            
            # Web server resources
            "apache2_site": {
                "ansible_module": "community.general.apache2_module",
                "property_mapping": {
                    "site_name": "name",
                    "enable": "state",
                    # Map Chef 'true' to Ansible 'present'
                    "value_mapping": {
                        "enable": {"true": "present", "false": "absent"}
                    }
                }
            },
            "nginx_site": {
                "ansible_module": "community.general.nginx_site",
                "property_mapping": {
                    "site_name": "name",
                    "enable": "state",
                    "value_mapping": {
                        "enable": {"true": "present", "false": "absent"}
                    }
                }
            },
            
            # System resources
            "cron_job": {
                "ansible_module": "ansible.builtin.cron",
                "property_mapping": {
                    "name": "name",
                    "command": "job",
                    "minute": "minute",
                    "hour": "hour",
                    "day": "day",
                    "month": "month",
                    "weekday": "weekday",
                    "user": "user"
                }
            },
            "systemd_unit": {
                "ansible_module": "ansible.builtin.systemd",
                "property_mapping": {
                    "unit_name": "name",
                    "action": "state",
                    "value_mapping": {
                        "action": {
                            "start": "started", 
                            "stop": "stopped",
                            "enable": "enabled",
                            "disable": "disabled"
                        }
                    }
                }
            }
        }
    
    def _load_custom_mappings(self, config_path: str) -> None:
        """Load custom resource mappings from a JSON file.
        
        Args:
            config_path: Path to a JSON mapping configuration file
        """
        try:
            with open(config_path, 'r') as f:
                custom_mappings = json.load(f)
            
            # Merge custom mappings with default mappings
            # Custom mappings take precedence
            for resource, mapping in custom_mappings.items():
                self.mappings[resource] = mapping
                
            logger.info(f"Loaded custom resource mappings from {config_path}")
        except Exception as e:
            logger.error(f"Failed to load custom resource mappings: {str(e)}")
    
    def get_mapping(self, resource_type: str) -> Optional[Dict[str, Any]]:
        """Get the Ansible mapping for a Chef custom resource.
        
        Args:
            resource_type: The Chef custom resource type
            
        Returns:
            A mapping dictionary or None if not found
        """
        return self.mappings.get(resource_type)
    
    def register_custom_handler(self, resource_type: str, handler_func):
        """Register a custom Python function to handle a specific resource type.
        
        This allows for complex transformations that can't be expressed in a simple mapping.
        
        Args:
            resource_type: The Chef custom resource type
            handler_func: A function that takes a Chef resource and returns Ansible tasks
        """
        self.custom_handlers[resource_type] = handler_func
        logger.info(f"Registered custom handler for {resource_type}")
    
    def has_custom_handler(self, resource_type: str) -> bool:
        """Check if a resource type has a custom handler.
        
        Args:
            resource_type: The Chef custom resource type
            
        Returns:
            True if a custom handler exists, False otherwise
        """
        return resource_type in self.custom_handlers
    
    def apply_custom_handler(self, resource_type: str, resource_data: Dict) -> List[Dict]:
        """Apply a custom handler to a resource.
        
        Args:
            resource_type: The Chef custom resource type
            resource_data: The Chef resource data
            
        Returns:
            A list of Ansible tasks
        """
        if not self.has_custom_handler(resource_type):
            return []
            
        handler = self.custom_handlers[resource_type]
        return handler(resource_data)
    
    def transform_resource(self, resource_type: str, resource_data: Dict) -> List[Dict]:
        """Transform a Chef custom resource to Ansible tasks.
        
        Args:
            resource_type: The Chef custom resource type
            resource_data: The Chef resource data
            
        Returns:
            A list of Ansible tasks
        """
        # First check if we have a custom handler
        if self.has_custom_handler(resource_type):
            return self.apply_custom_handler(resource_type, resource_data)
        
        # Then check if we have a mapping
        mapping = self.get_mapping(resource_type)
        if not mapping:
            logger.warning(f"No mapping found for resource type: {resource_type}")
            # Return a commented task as a placeholder
            return [{
                "name": f"TODO: Convert Chef custom resource '{resource_type}'",
                "ansible.builtin.debug":
                    {"msg": f"Chef custom resource '{resource_type}' requires manual conversion"}
            }]
        
        # Apply the mapping
        ansible_module = mapping.get("ansible_module")
        property_mapping = mapping.get("property_mapping", {})
        
        ansible_task = {
            "name": f"Converted from Chef custom resource '{resource_type}'",
            ansible_module: {}
        }
        
        # Map properties
        for chef_prop, ansible_prop in property_mapping.items():
            if chef_prop == "value_mapping":
                continue
                
            if chef_prop in resource_data:
                value = resource_data[chef_prop]
                
                # Apply value mapping if defined
                value_mapping = property_mapping.get("value_mapping", {}).get(chef_prop, {})
                if value_mapping and str(value).lower() in value_mapping:
                    value = value_mapping[str(value).lower()]
                    
                ansible_task[ansible_module][ansible_prop] = value
        
        return [ansible_task]
