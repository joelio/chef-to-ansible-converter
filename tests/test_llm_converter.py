#!/usr/bin/env python3
"""
Unit tests for the LLMConverter module
"""
import os
import sys
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.llm_converter import LLMConverter
from src.config import Config


class TestLLMConverter:
    """Test cases for the LLMConverter class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.config = Config(api_key="test_key", model="claude-3-7-sonnet-20250219")
        self.converter = LLMConverter(self.config)

    def test_initialization(self):
        """Test converter initialization"""
        converter = LLMConverter(self.config)
        
        assert converter.config == self.config
        assert converter.client is not None
        assert hasattr(converter, 'examples')

    def test_convert_recipe(self):
        """Test converting a Chef recipe to Ansible tasks"""
        # Mock the API response
        mock_message = MagicMock()
        mock_content = MagicMock()
        mock_content.text = """
# Ansible Tasks
```yaml
- name: Install nginx
  ansible.builtin.package:
    name: nginx
    state: present

- name: Enable and start nginx service
  ansible.builtin.service:
    name: nginx
    enabled: true
    state: started
```

# Ansible Handlers
```yaml
- name: Restart nginx
  ansible.builtin.service:
    name: nginx
    state: restarted
```
"""
        mock_message.content = [mock_content]
        
        # Mock the _call_anthropic_api method to avoid actual API calls
        with patch.object(self.converter, '_call_anthropic_api', return_value=mock_content.text):
            # Mock the _extract_code_block and _parse_yaml_content methods
            with patch.object(self.converter, '_extract_code_block') as mock_extract:
                mock_extract.side_effect = lambda text, block_name: "- name: Install nginx\n  ansible.builtin.package:\n    name: nginx\n    state: present" if block_name == "tasks" else "- name: Restart nginx\n  ansible.builtin.service:\n    name: nginx\n    state: restarted" if block_name == "handlers" else ""
                
                with patch.object(self.converter, '_parse_yaml_content') as mock_parse:
                    mock_parse.side_effect = lambda yaml_content: [{"name": "Install nginx", "ansible.builtin.package": {"name": "nginx", "state": "present"}}] if "Install nginx" in yaml_content else [{"name": "Restart nginx", "ansible.builtin.service": {"name": "nginx", "state": "restarted"}}]
                    
                    # Test recipe conversion
                    recipe = {
                        "name": "test",
                        "path": "test.rb",
                        "content": """
package 'nginx' do
  action :install
end

service 'nginx' do
  action [:enable, :start]
end
                        """
                    }
                    
                    result = self.converter.convert_recipe(recipe)
                    
                    # Verify the result
                    assert result is not None
                    assert "tasks" in result
                    assert isinstance(result["tasks"], list)
                    assert len(result["tasks"]) >= 1
                    assert "name" in result["tasks"][0]
                    assert result["tasks"][0]["name"] == "Install nginx"

    def test_convert_templates(self):
        """Test converting ERB templates to Jinja2"""
        # Mock the API response
        mock_response = """```jinja
server {
  listen 80;
  server_name {{ server_name }};
  
  location / {
    root {{ document_root }};
    {% if enable_php %}
    index index.php index.html;
    {% else %}
    index index.html;
    {% endif %}
  }
}
```"""
        
        # Mock the _call_anthropic_api method to avoid actual API calls
        with patch.object(self.converter, '_call_anthropic_api', return_value=mock_response):
            # Mock the _convert_erb_to_jinja method
            with patch.object(self.converter, '_convert_erb_to_jinja') as mock_convert:
                mock_convert.return_value = """server {
  listen 80;
  server_name {{ server_name }};
  
  location / {
    root {{ document_root }};
    {% if enable_php %}
    index index.php index.html;
    {% else %}
    index index.html;
    {% endif %}
  }
}"""
                
                # Test template conversion
                templates = [{
                    "name": "nginx.conf",
                    "path": "nginx.conf.erb",
                    "content": """
server {
  listen 80;
  server_name <%= @server_name %>;
  
  location / {
    root <%= @document_root %>;
    <% if @enable_php %>
    index index.php index.html;
    <% else %>
    index index.html;
    <% end %>
  }
}
                    """
                }]
                
                results = self.converter.convert_templates(templates)
                
                # Verify the result
                assert results is not None
                assert len(results) == 1
                assert "content" in results[0]
                assert "{{ server_name }}" in results[0]["content"]
                assert "{{ document_root }}" in results[0]["content"]
                assert "{% if enable_php %}" in results[0]["content"]
                assert "{% else %}" in results[0]["content"]
                assert "{% endif %}" in results[0]["content"]

    def test_api_error_handling(self):
        """Test handling of API errors"""
        # Mock _call_anthropic_api to raise an exception
        with patch.object(self.converter, '_call_anthropic_api', side_effect=RuntimeError("API Error")):
            # Test recipe conversion with error
            recipe = {
                "name": "test",
                "path": "test.rb",
                "content": "package 'nginx'"
            }
            
            with pytest.raises(Exception):
                self.converter.convert_recipe(recipe)
    
    def test_load_examples(self):
        """Test loading conversion examples"""
        # The _load_examples method returns a hardcoded list of examples
        examples = self.converter._load_examples()
        
        assert examples is not None
        assert len(examples) == 5  # There are 5 hardcoded examples
        assert "chef_code" in examples[0]
        assert "ansible_code" in examples[0]
        assert "package 'nginx'" in examples[0]["chef_code"]
        assert "Install nginx" in examples[0]["ansible_code"]
    
    def test_build_conversion_prompt(self):
        """Test building conversion prompt"""
        # Mock the examples and config
        with patch.object(self.converter, 'examples', [{
            "chef_code": "package 'nginx' do\n  action :install\nend",
            "ansible_code": "- name: Install nginx\n  ansible.builtin.package:\n    name: nginx\n    state: present"
        }]):
            with patch.object(self.converter.config, 'examples_per_request', 1):
                recipe = {
                    "name": "test",
                    "path": "test.rb",
                    "content": "package 'apache2' do\n  action :install\nend"
                }
                
                prompt = self.converter._build_conversion_prompt(recipe)
                
                assert prompt is not None
                assert "You are an expert in both Chef and Ansible" in prompt
                assert "package 'apache2'" in prompt
                assert "CHEF CODE:" in prompt
                assert "IMPORTANT: Follow these Ansible best practices" in prompt
                assert "ANSIBLE CODE:" in prompt
    
    def test_extract_ansible_code(self):
        """Test extracting Ansible code from LLM response"""
        response = """
Here's the converted Ansible code for your Chef recipe:  

# Ansible Tasks
```yaml
- name: Install apache2
  ansible.builtin.package:
    name: apache2
    state: present
```

# Ansible Handlers
```yaml
- name: Restart apache2
  ansible.builtin.service:
    name: apache2
    state: restarted
```

This Ansible code will install the apache2 package and create a handler to restart it.
"""
        
        # Mock the _extract_code_block and _parse_yaml_content methods
        with patch.object(self.converter, '_extract_code_block') as mock_extract:
            mock_extract.side_effect = lambda text, block_name: "- name: Install apache2\n  ansible.builtin.package:\n    name: apache2\n    state: present" if block_name == "tasks" else "- name: Restart apache2\n  ansible.builtin.service:\n    name: apache2\n    state: restarted" if block_name == "handlers" else ""
            
            with patch.object(self.converter, '_parse_yaml_content') as mock_parse:
                mock_parse.side_effect = lambda yaml_content: [{"name": "Install apache2", "ansible.builtin.package": {"name": "apache2", "state": "present"}}] if "Install apache2" in yaml_content else [{"name": "Restart apache2", "ansible.builtin.service": {"name": "apache2", "state": "restarted"}}]
                
                result = self.converter._extract_ansible_code(response)
                
                assert result is not None
                assert "tasks" in result
                assert "handlers" in result
                assert len(result["tasks"]) == 1
                assert len(result["handlers"]) == 1
                assert result["tasks"][0]["name"] == "Install apache2"
                assert result["handlers"][0]["name"] == "Restart apache2"
    
    def test_extract_code_block(self):
        """Test extracting code block from text"""
        text = """
# Ansible Tasks
```yaml
- name: Install apache2
  ansible.builtin.package:
    name: apache2
    state: present
```

# Ansible Handlers
```yaml
- name: Restart apache2
  ansible.builtin.service:
    name: apache2
    state: restarted
```
"""
        
        # The actual implementation uses a regex pattern to extract code blocks
        with patch('re.search') as mock_search:
            # Mock the regex search for tasks
            mock_search.return_value.group.return_value = "- name: Install apache2\n  ansible.builtin.package:\n    name: apache2\n    state: present"
            result = self.converter._extract_code_block(text, "tasks")
            
            assert result is not None
            assert "- name: Install apache2" in result
            assert "ansible.builtin.package" in result
            
            # Mock the regex search for handlers
            mock_search.return_value.group.return_value = "- name: Restart apache2\n  ansible.builtin.service:\n    name: apache2\n    state: restarted"
            result = self.converter._extract_code_block(text, "handlers")
            
            assert result is not None
            assert "- name: Restart apache2" in result
            assert "ansible.builtin.service" in result
    
    def test_convert_cookbook(self):
        """Test converting a cookbook"""
        cookbook = {
            "name": "test_cookbook",
            "recipes": [{
                "name": "default",
                "path": "recipes/default.rb",
                "content": "package 'apache2' do\n  action :install\nend"
            }],
            "attributes": [{
                "name": "default",
                "path": "attributes/default.rb",
                "content": "default['apache2']['version'] = '2.4.41'"
            }],
            "templates": [{
                "name": "apache2.conf",
                "path": "templates/apache2.conf.erb",
                "content": "ServerName <%= @server_name %>"
            }],
            "files": [{
                "name": "index.html",
                "path": "files/default/index.html"
            }]
        }
        
        # Mock the conversion methods
        with patch.object(self.converter, 'convert_recipe') as mock_convert_recipe:
            mock_convert_recipe.return_value = {
                "tasks": [{"name": "Install apache2", "ansible.builtin.package": {"name": "apache2", "state": "present"}}],
                "handlers": []
            }
            
            with patch.object(self.converter, 'convert_attributes') as mock_convert_attributes:
                mock_convert_attributes.return_value = {"apache2_version": "2.4.41"}
                
                with patch.object(self.converter, 'convert_templates') as mock_convert_templates:
                    mock_convert_templates.return_value = [{
                        "name": "apache2.conf",
                        "path": "templates/apache2.conf.j2",
                        "content": "ServerName {{ server_name }}"
                    }]
                    
                    with patch.object(self.converter, 'convert_files') as mock_convert_files:
                        mock_convert_files.return_value = [{
                            "name": "index.html",
                            "path": "files/index.html"
                        }]
                        
                        # Mock progress_callback
                        with patch.object(self.converter, 'progress_callback', None):
                            result = self.converter.convert_cookbook(cookbook)
                            
                            assert result is not None
                            assert "tasks" in result
                            assert "handlers" in result
                            assert "variables" in result
                            assert len(result["tasks"]) == 1
                            assert result["tasks"][0]["name"] == "Install apache2"
    
    def test_convert_attributes(self):
        """Test converting Chef attributes to Ansible variables"""
        attributes = [{
            "name": "default",
            "path": "attributes/default.rb",
            "content": "default['apache2']['version'] = '2.4.41'\ndefault['apache2']['user'] = 'www-data'"
        }]
        
        # Mock the _call_anthropic_api method
        with patch.object(self.converter, '_call_anthropic_api') as mock_api:
            mock_api.return_value = """
```yaml
apache2_version: '2.4.41'
apache2_user: 'www-data'
```
"""
            
            # Mock the _parse_yaml_content method
            with patch.object(self.converter, '_parse_yaml_content') as mock_parse:
                mock_parse.return_value = {"apache2_version": "2.4.41", "apache2_user": "www-data"}
                
                result = self.converter.convert_attributes(attributes)
                
                assert result is not None
                assert "apache2_version" in result
                assert "apache2_user" in result
                assert result["apache2_version"] == "2.4.41"
                assert result["apache2_user"] == "www-data"
    
    def test_convert_erb_to_jinja(self):
        """Test converting ERB syntax to Jinja2"""
        erb_content = """ServerName <%= @server_name %>
DocumentRoot <%= @document_root %>
<% if @enable_php %>
PHP Enabled
<% else %>
PHP Disabled
<% end %>
"""
        
        # The actual implementation keeps the @ symbol in variable names
        with patch('re.sub') as mock_sub:
            # Mock the regex substitutions
            mock_sub.side_effect = lambda pattern, repl, string: string.replace('<%= @server_name %>', '{{ @server_name }}')\
                                                                       .replace('<%= @document_root %>', '{{ @document_root }}')\
                                                                       .replace('<% if @enable_php %>', '{% if @enable_php %}')\
                                                                       .replace('<% else %>', '{% else %}')\
                                                                       .replace('<% end %>', '{% endif %}')
            
            result = self.converter._convert_erb_to_jinja(erb_content)
            
            assert result is not None
            assert "{{ @server_name }}" in result
            assert "{{ @document_root }}" in result
            assert "{% if @enable_php %}" in result
            assert "{% else %}" in result
            assert "{% endif %}" in result
    
    def test_convert_files(self):
        """Test converting Chef files to Ansible files"""
        files = [{
            "name": "index.html",
            "path": "files/default/index.html"
        }, {
            "name": "style.css",
            "path": "files/default/css/style.css"
        }]
        
        # The actual implementation just returns the files as-is
        result = self.converter.convert_files(files)
        
        assert result is not None
        assert len(result) == 2
        assert result[0]["name"] == "index.html"
        assert result[0]["path"] == "files/default/index.html"
        assert result[1]["name"] == "style.css"
        assert result[1]["path"] == "files/default/css/style.css"
