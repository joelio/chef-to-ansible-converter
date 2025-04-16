"""
Integration tests for custom resource handling in the Chef to Ansible converter.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.config import Config
from src.llm_converter import LLMConverter


class TestCustomResourceIntegration(unittest.TestCase):
    """Integration tests for custom resource handling."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock config
        self.config = Config(api_key="test_key")
        
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        
        # Create a sample Chef recipe with custom resources
        self.chef_recipe = """
# Sample Chef recipe with custom resources
mysql_database 'myapp' do
  database_name 'myapp_production'
  connection host: 'localhost', port: 3306
  user 'db_admin'
  password 'secure_password'
  action :create
end

nginx_site 'myapp' do
  site_name 'myapp.example.com'
  template 'nginx.conf.erb'
  enable true
end

docker_container 'web_app' do
  container_name 'web_app'
  image 'nginx:latest'
  ports ['80:80', '443:443']
  volumes ['/data:/data']
  env ['NGINX_HOST=example.com', 'NGINX_PORT=80']
  restart_policy 'always'
end
"""
        
        # Write the Chef recipe to a file
        self.recipe_path = self.test_dir / "recipe.rb"
        with open(self.recipe_path, 'w') as f:
            f.write(self.chef_recipe)
        
        # Create a custom resource mapping file
        self.mapping_path = self.test_dir / "mappings.json"
        self.test_mappings = {
            "mysql_database": {
                "ansible_module": "community.mysql.mysql_db",
                "property_mapping": {
                    "database_name": "name",
                    "connection": "login_host",
                    "user": "login_user",
                    "password": "login_password"
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
        
        # Mock LLM response for the test
        self.mock_llm_response = """
Here's the conversion of the Chef recipe to Ansible:

Tasks:
```yaml
- name: Create MySQL database
  ansible.builtin.debug:
    msg: "Chef custom resource 'mysql_database' requires manual conversion"
  vars:
    database_name: myapp_production
    connection: localhost
    user: db_admin
    password: secure_password

- name: Configure Nginx site
  ansible.builtin.debug:
    msg: "Chef custom resource 'nginx_site' requires manual conversion"
  vars:
    site_name: myapp.example.com
    template: nginx.conf.erb
    enable: true

- name: Run Docker container
  ansible.builtin.debug:
    msg: "Chef custom resource 'docker_container' requires manual conversion"
  vars:
    container_name: web_app
    image: nginx:latest
    ports: ['80:80', '443:443']
    volumes: ['/data:/data']
    env: ['NGINX_HOST=example.com', 'NGINX_PORT=80']
    restart_policy: always
```

Handlers:
```yaml
# No handlers in this recipe
```

Variables:
```yaml
# Define variables for the Ansible role
mysql_host: localhost
mysql_port: 3306
nginx_config_dir: /etc/nginx/sites-available
docker_host: unix:///var/run/docker.sock
```
"""
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up the temporary directory
        self.temp_dir.cleanup()
    
    @patch('anthropic.Anthropic')
    def test_end_to_end_conversion(self, mock_anthropic):
        """Test end-to-end conversion of a Chef recipe with custom resources."""
        # Mock the Anthropic client
        mock_client = MagicMock()
        # Create a mock message object with the expected structure
        mock_message = MagicMock()
        mock_message.content = [
            MagicMock(text=self.mock_llm_response)
        ]
        # Make the messages.create method return our mock message
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.return_value = mock_client
        
        # Create a converter instance
        converter = LLMConverter(self.config)
        
        # Mock the recipe data
        recipe_data = {
            "path": str(self.recipe_path),
            "content": self.chef_recipe,
            "name": "test_recipe",
            "cookbook": "test_cookbook"
        }
        
        # Convert the recipe
        result = converter.convert_recipe(recipe_data)
        
        # Check that we have the expected tasks
        self.assertEqual(len(result["tasks"]), 3)
        
        # Check the MySQL database task
        mysql_task = result["tasks"][0]
        self.assertIn("community.mysql.mysql_db", mysql_task)
        self.assertEqual(mysql_task["community.mysql.mysql_db"]["name"], "myapp_production")
        self.assertEqual(mysql_task["community.mysql.mysql_db"]["login_host"], "localhost")
        self.assertEqual(mysql_task["community.mysql.mysql_db"]["login_user"], "db_admin")
        self.assertEqual(mysql_task["community.mysql.mysql_db"]["login_password"], "secure_password")
        
        # Check the Nginx site task
        nginx_task = result["tasks"][1]
        self.assertIn("community.general.nginx_site", nginx_task)
        self.assertEqual(nginx_task["community.general.nginx_site"]["name"], "myapp.example.com")
        self.assertEqual(nginx_task["community.general.nginx_site"]["state"], "present")
        
        # Check the Docker container task
        docker_task = result["tasks"][2]
        self.assertIn("community.docker.docker_container", docker_task)
        self.assertEqual(docker_task["community.docker.docker_container"]["name"], "web_app")
        self.assertEqual(docker_task["community.docker.docker_container"]["image"], "nginx:latest")
        self.assertEqual(docker_task["community.docker.docker_container"]["ports"], ['80:80', '443:443'])
        self.assertEqual(docker_task["community.docker.docker_container"]["volumes"], ['/data:/data'])
        self.assertEqual(docker_task["community.docker.docker_container"]["env"], 
                         ['NGINX_HOST=example.com', 'NGINX_PORT=80'])
        self.assertEqual(docker_task["community.docker.docker_container"]["restart_policy"], "always")


if __name__ == '__main__':
    unittest.main()
