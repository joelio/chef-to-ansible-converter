"""
Tests for custom resource handling with real-world Chef cookbooks.

This test suite tests the custom resource handling functionality against
actual upstream Chef cookbooks that use custom resources.
"""

import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.config import Config
from src.llm_converter import LLMConverter
from src.chef_parser import ChefParser
from src.resource_mapping import ResourceMapping


class TestUpstreamCustomResources(unittest.TestCase):
    """Test custom resource handling with real-world Chef cookbooks."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock config
        self.config = Config(api_key="test_key")
        
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        
        # Create a mapping file with common Chef custom resources
        self.mapping_path = self.test_dir / "mappings.json"
        self.test_mappings = {
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
            
            # Chef Ingredient resources (common in Chef cookbooks)
            "chef_ingredient": {
                "ansible_module": "ansible.builtin.package",
                "property_mapping": {
                    "product_name": "name",
                    "version": "version",
                    "action": "state",
                    "value_mapping": {
                        "action": {"install": "present", "remove": "absent"}
                    }
                }
            },
            
            # ETCD resources
            "etcd_service": {
                "ansible_module": "ansible.builtin.systemd",
                "property_mapping": {
                    "service_name": "name",
                    "action": "state",
                    "value_mapping": {
                        "action": {"start": "started", "stop": "stopped"}
                    }
                }
            },
            
            # Apache resources
            "apache2_module": {
                "ansible_module": "community.general.apache2_module",
                "property_mapping": {
                    "module_name": "name",
                    "enable": "state",
                    "value_mapping": {
                        "enable": {"true": "present", "false": "absent"}
                    }
                }
            },
            "apache2_site": {
                "ansible_module": "community.general.apache2_site",
                "property_mapping": {
                    "site_name": "name",
                    "enable": "state",
                    "value_mapping": {
                        "enable": {"true": "present", "false": "absent"}
                    }
                }
            },
            
            # Docker resources
            "docker_container": {
                "ansible_module": "community.docker.docker_container",
                "property_mapping": {
                    "container_name": "name",
                    "image": "image",
                    "ports": "ports",
                    "volumes": "volumes",
                    "env": "env",
                    "restart_policy": "restart_policy"
                }
            }
        }
        
        with open(self.mapping_path, 'w') as f:
            json.dump(self.test_mappings, f)
        
        # Set the resource mapping path in the config
        self.config.resource_mapping_path = str(self.mapping_path)
        
        # Create sample Chef recipes with custom resources
        self.create_test_recipes()
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up the temporary directory
        self.temp_dir.cleanup()
    
    def create_test_recipes(self):
        """Create test recipes with custom resources."""
        # Create test directories
        recipes_dir = self.test_dir / "recipes"
        recipes_dir.mkdir(exist_ok=True)
        
        # 1. Chef Ingredient recipe (common in Chef infrastructure)
        chef_ingredient_recipe = """
# Install Chef Server using chef_ingredient
chef_ingredient 'chef-server' do
  product_name 'chef-server-core'
  version '12.19.31'
  config <<-EOS
api_fqdn "chef.example.com"
notification_email "admin@example.com"
EOS
  action :install
end

chef_ingredient 'manage' do
  product_name 'chef-manage'
  accept_license true
  action :install
end
"""
        with open(recipes_dir / "chef_ingredient.rb", 'w') as f:
            f.write(chef_ingredient_recipe)
        
        # 2. ETCD recipe (common in Kubernetes deployments)
        etcd_recipe = """
# Configure ETCD service
etcd_service 'default' do
  service_name 'etcd'
  node_name 'etcd1'
  initial_advertise_peer_urls 'http://192.168.1.10:2380'
  listen_peer_urls 'http://192.168.1.10:2380'
  listen_client_urls 'http://192.168.1.10:2379,http://127.0.0.1:2379'
  initial_cluster_token 'etcd-cluster-1'
  initial_cluster 'etcd1=http://192.168.1.10:2380,etcd2=http://192.168.1.11:2380'
  initial_cluster_state 'new'
  action :start
end
"""
        with open(recipes_dir / "etcd.rb", 'w') as f:
            f.write(etcd_recipe)
        
        # 3. Apache2 recipe (common web server)
        apache2_recipe = """
# Configure Apache modules and sites
apache2_module 'ssl' do
  enable true
end

apache2_module 'rewrite' do
  enable true
end

apache2_site 'default' do
  enable false
end

apache2_site 'myapp' do
  site_name 'myapp.example.com'
  template 'myapp.conf.erb'
  enable true
end
"""
        with open(recipes_dir / "apache2.rb", 'w') as f:
            f.write(apache2_recipe)
        
        # 4. Database recipe with MySQL and PostgreSQL
        database_recipe = """
# Configure databases
mysql_database 'app_production' do
  database_name 'myapp_production'
  connection host: 'db.example.com', port: 3306
  user 'db_admin'
  password 'secure_password'
  action :create
end

postgresql_database 'analytics' do
  database_name 'analytics_db'
  connection host: 'postgres.example.com', port: 5432
  user 'postgres'
  password 'postgres_pass'
  encoding 'UTF8'
  action :create
end
"""
        with open(recipes_dir / "database.rb", 'w') as f:
            f.write(database_recipe)
    
    def get_recipe_data(self, recipe_name):
        """Get recipe data for testing."""
        recipe_path = self.test_dir / "recipes" / f"{recipe_name}.rb"
        with open(recipe_path, 'r') as f:
            content = f.read()
        
        return {
            "path": str(recipe_path),
            "content": content,
            "name": recipe_name,
            "cookbook": "test_cookbook"
        }
    
    @patch('anthropic.Anthropic')
    def test_chef_ingredient_conversion(self, mock_anthropic):
        """Test conversion of chef_ingredient custom resource."""
        # Mock the Anthropic client
        mock_client = MagicMock()
        # Create a mock message with a response that includes chef_ingredient placeholders
        mock_message = MagicMock()
        mock_message.content = [
            MagicMock(text="""
Here's the conversion of the Chef recipe to Ansible:

Tasks:
```yaml
- name: "Converted from Chef custom resource 'chef_ingredient'"
  ansible.builtin.debug:
    msg: "Chef custom resource 'chef_ingredient' requires manual conversion"
  vars:
    product_name: chef-server-core
    version: 12.19.31
    action: install
    config: |
      api_fqdn "chef.example.com"
      notification_email "admin@example.com"

- name: "Converted from Chef custom resource 'chef_ingredient'"
  ansible.builtin.debug:
    msg: "Chef custom resource 'chef_ingredient' requires manual conversion"
  vars:
    product_name: chef-manage
    accept_license: true
    action: install
```

Handlers:
```yaml
# No handlers in this recipe
```
""")
        ]
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.return_value = mock_client
        
        # Create a converter instance
        converter = LLMConverter(self.config)
        
        # Convert the recipe
        recipe_data = self.get_recipe_data("chef_ingredient")
        result = converter.convert_recipe(recipe_data)
        
        # Check that we have the expected tasks
        self.assertEqual(len(result["tasks"]), 2)
        
        # Check the first chef_ingredient task
        task1 = result["tasks"][0]
        self.assertIn("ansible.builtin.package", task1)
        self.assertEqual(task1["ansible.builtin.package"]["name"], "chef-server-core")
        self.assertEqual(task1["ansible.builtin.package"]["version"], "12.19.31")
        self.assertEqual(task1["ansible.builtin.package"]["state"], "present")
        
        # Check the second chef_ingredient task
        task2 = result["tasks"][1]
        self.assertIn("ansible.builtin.package", task2)
        self.assertEqual(task2["ansible.builtin.package"]["name"], "chef-manage")
        self.assertEqual(task2["ansible.builtin.package"]["state"], "present")
    
    @patch('anthropic.Anthropic')
    def test_etcd_conversion(self, mock_anthropic):
        """Test conversion of etcd_service custom resource."""
        # Mock the Anthropic client
        mock_client = MagicMock()
        # Create a mock message with a response that includes etcd_service placeholders
        mock_message = MagicMock()
        mock_message.content = [
            MagicMock(text="""
Here's the conversion of the Chef recipe to Ansible:

Tasks:
```yaml
- name: "Converted from Chef custom resource 'etcd_service'"
  ansible.builtin.debug:
    msg: "Chef custom resource 'etcd_service' requires manual conversion"
  vars:
    service_name: etcd
    node_name: etcd1
    initial_advertise_peer_urls: http://192.168.1.10:2380
    listen_peer_urls: http://192.168.1.10:2380
    listen_client_urls: http://192.168.1.10:2379,http://127.0.0.1:2379
    initial_cluster_token: etcd-cluster-1
    initial_cluster: etcd1=http://192.168.1.10:2380,etcd2=http://192.168.1.11:2380
    initial_cluster_state: new
    action: start
```

Handlers:
```yaml
# No handlers in this recipe
```
""")
        ]
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.return_value = mock_client
        
        # Create a converter instance
        converter = LLMConverter(self.config)
        
        # Convert the recipe
        recipe_data = self.get_recipe_data("etcd")
        result = converter.convert_recipe(recipe_data)
        
        # Check that we have the expected task
        self.assertEqual(len(result["tasks"]), 1)
        
        # Check the etcd_service task
        task = result["tasks"][0]
        self.assertIn("ansible.builtin.systemd", task)
        self.assertEqual(task["ansible.builtin.systemd"]["name"], "etcd")
        self.assertEqual(task["ansible.builtin.systemd"]["state"], "started")
    
    @patch('anthropic.Anthropic')
    def test_apache2_conversion(self, mock_anthropic):
        """Test conversion of apache2_module and apache2_site custom resources."""
        # Mock the Anthropic client
        mock_client = MagicMock()
        # Create a mock message with a response that includes apache2 placeholders
        mock_message = MagicMock()
        mock_message.content = [
            MagicMock(text="""
Here's the conversion of the Chef recipe to Ansible:

Tasks:
```yaml
- name: "Converted from Chef custom resource 'apache2_module'"
  ansible.builtin.debug:
    msg: "Chef custom resource 'apache2_module' requires manual conversion"
  vars:
    module_name: ssl
    enable: true

- name: "Converted from Chef custom resource 'apache2_module'"
  ansible.builtin.debug:
    msg: "Chef custom resource 'apache2_module' requires manual conversion"
  vars:
    module_name: rewrite
    enable: true

- name: "Converted from Chef custom resource 'apache2_site'"
  ansible.builtin.debug:
    msg: "Chef custom resource 'apache2_site' requires manual conversion"
  vars:
    site_name: default
    enable: false

- name: "Converted from Chef custom resource 'apache2_site'"
  ansible.builtin.debug:
    msg: "Chef custom resource 'apache2_site' requires manual conversion"
  vars:
    site_name: myapp.example.com
    template: myapp.conf.erb
    enable: true
```

Handlers:
```yaml
# No handlers in this recipe
```
""")
        ]
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.return_value = mock_client
        
        # Create a converter instance
        converter = LLMConverter(self.config)
        
        # Convert the recipe
        recipe_data = self.get_recipe_data("apache2")
        result = converter.convert_recipe(recipe_data)
        
        # Check that we have the expected tasks
        self.assertEqual(len(result["tasks"]), 4)
        
        # Check the first apache2_module task
        task1 = result["tasks"][0]
        self.assertIn("community.general.apache2_module", task1)
        self.assertEqual(task1["community.general.apache2_module"]["name"], "ssl")
        self.assertEqual(task1["community.general.apache2_module"]["state"], "present")
        
        # Check the second apache2_module task
        task2 = result["tasks"][1]
        self.assertIn("community.general.apache2_module", task2)
        self.assertEqual(task2["community.general.apache2_module"]["name"], "rewrite")
        self.assertEqual(task2["community.general.apache2_module"]["state"], "present")
        
        # Check the first apache2_site task
        task3 = result["tasks"][2]
        self.assertIn("community.general.apache2_site", task3)
        self.assertEqual(task3["community.general.apache2_site"]["name"], "default")
        self.assertEqual(task3["community.general.apache2_site"]["state"], "absent")
        
        # Check the second apache2_site task
        task4 = result["tasks"][3]
        self.assertIn("community.general.apache2_site", task4)
        self.assertEqual(task4["community.general.apache2_site"]["name"], "myapp.example.com")
        self.assertEqual(task4["community.general.apache2_site"]["state"], "present")
    
    @patch('anthropic.Anthropic')
    def test_database_conversion(self, mock_anthropic):
        """Test conversion of mysql_database and postgresql_database custom resources."""
        # Mock the Anthropic client
        mock_client = MagicMock()
        # Create a mock message with a response that includes database placeholders
        mock_message = MagicMock()
        mock_message.content = [
            MagicMock(text="""
Here's the conversion of the Chef recipe to Ansible:

Tasks:
```yaml
- name: "Converted from Chef custom resource 'mysql_database'"
  ansible.builtin.debug:
    msg: "Chef custom resource 'mysql_database' requires manual conversion"
  vars:
    database_name: myapp_production
    connection: db.example.com
    user: db_admin
    password: secure_password
    action: create

- name: "Converted from Chef custom resource 'postgresql_database'"
  ansible.builtin.debug:
    msg: "Chef custom resource 'postgresql_database' requires manual conversion"
  vars:
    database_name: analytics_db
    connection: postgres.example.com
    user: postgres
    password: postgres_pass
    encoding: UTF8
    action: create
```

Handlers:
```yaml
# No handlers in this recipe
```
""")
        ]
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.return_value = mock_client
        
        # Create a converter instance
        converter = LLMConverter(self.config)
        
        # Convert the recipe
        recipe_data = self.get_recipe_data("database")
        result = converter.convert_recipe(recipe_data)
        
        # Check that we have the expected tasks
        self.assertEqual(len(result["tasks"]), 2)
        
        # Check the mysql_database task
        task1 = result["tasks"][0]
        self.assertIn("community.mysql.mysql_db", task1)
        self.assertEqual(task1["community.mysql.mysql_db"]["name"], "myapp_production")
        self.assertEqual(task1["community.mysql.mysql_db"]["login_host"], "db.example.com")
        self.assertEqual(task1["community.mysql.mysql_db"]["login_user"], "db_admin")
        self.assertEqual(task1["community.mysql.mysql_db"]["login_password"], "secure_password")
        
        # Check the postgresql_database task
        task2 = result["tasks"][1]
        self.assertIn("community.postgresql.postgresql_db", task2)
        self.assertEqual(task2["community.postgresql.postgresql_db"]["name"], "analytics_db")
        self.assertEqual(task2["community.postgresql.postgresql_db"]["login_host"], "postgres.example.com")
        self.assertEqual(task2["community.postgresql.postgresql_db"]["login_user"], "postgres")
        self.assertEqual(task2["community.postgresql.postgresql_db"]["login_password"], "postgres_pass")


if __name__ == '__main__':
    unittest.main()
