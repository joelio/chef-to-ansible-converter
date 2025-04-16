#!/usr/bin/env python3
"""
Unit tests for the ChefParser module
"""
import os
import sys
import pytest
import json
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

# Add src directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.chef_parser import ChefParser


class TestChefParser:
    """Test cases for the ChefParser class"""

    def test_parse_recipes(self):
        """Test parsing recipes"""
        parser = ChefParser()
        
        chef_recipe = """
        package 'nginx' do
          action :install
        end

        service 'nginx' do
          action [:enable, :start]
        end
        """
        
        # Mock Path.exists and Path.glob
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.glob") as mock_glob:
                mock_glob.return_value = [Path("recipes/default.rb")]
                
                # Mock open to return our test recipe
                with patch("builtins.open", mock_open(read_data=chef_recipe)):
                    result = parser._parse_recipes(Path("recipes"))
                    
                    assert result is not None
                    assert len(result) == 1
                    assert "content" in result[0]
                    assert "package" in result[0]["content"]
                    assert "service" in result[0]["content"]

    def test_find_cookbooks(self):
        """Test finding cookbooks in a repository"""
        parser = ChefParser()
        
        # Mock Path.glob to return a list of metadata files
        with patch("pathlib.Path.glob") as mock_glob:
            mock_glob.return_value = [
                Path("/repo/cookbook1/metadata.rb"),
                Path("/repo/cookbook2/metadata.rb")
            ]
            
            # Mock _extract_cookbook_name to return cookbook names
            with patch.object(parser, "_extract_cookbook_name") as mock_extract:
                mock_extract.side_effect = ["cookbook1", "cookbook2"]
                
                cookbooks = parser.find_cookbooks("/repo")
                
                assert len(cookbooks) == 2
                assert cookbooks[0]["name"] == "cookbook1"
                assert cookbooks[1]["name"] == "cookbook2"

    def test_find_templates(self):
        """Test finding templates"""
        parser = ChefParser()
        
        erb_template = """
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
        
        # Mock Path.exists and Path.glob
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.glob") as mock_glob:
                # The actual implementation uses glob('**/*') and then checks is_file()
                mock_file = MagicMock()
                mock_file.is_file.return_value = True
                mock_file.name = "nginx.conf.erb"
                mock_file.relative_to.return_value = Path("default/nginx.conf.erb")
                mock_glob.return_value = [mock_file]
                
                # Mock open to return our test template
                with patch("builtins.open", mock_open(read_data=erb_template)):
                    result = parser._find_templates(Path("templates"))
                    
                    assert result is not None
                    assert len(result) == 1
                    assert "content" in result[0]
                    assert "name" in result[0]
                    assert "path" in result[0]
                    assert result[0]["name"] == "nginx.conf.erb"

    def test_parse_cookbook(self):
        """Test parsing cookbook"""
        parser = ChefParser()
        
        cookbook_path = Path("/path/to/cookbook")
        
        # Mock all the methods called by parse_cookbook
        with patch.object(parser, "_parse_metadata", return_value={"name": "test_cookbook"}):
            with patch.object(parser, "_parse_recipes", return_value=[{"name": "default", "path": "recipes/default.rb"}]):
                with patch.object(parser, "_parse_attributes", return_value=[]):
                    with patch.object(parser, "_find_templates", return_value=[{"name": "nginx.conf", "path": "templates/nginx.conf.erb"}]):
                        with patch.object(parser, "_find_files", return_value=[]):
                            with patch.object(parser, "_parse_resources", return_value=[]):
                                with patch.object(parser, "_parse_libraries", return_value=[]):
                                    with patch.object(parser, "_find_data_bags", return_value=[]):
                                        result = parser.parse_cookbook(cookbook_path)
                                        
                                        assert result is not None
                                        assert "name" in result
                                        assert "recipes" in result
                                        assert "templates" in result
                                        assert len(result["recipes"]) == 1
                                        assert len(result["templates"]) == 1
    
    def test_extract_resources(self):
        """Test extracting resources from recipe content"""
        parser = ChefParser()
        
        recipe_content = """
        package 'nginx' do
          action :install
          version '1.18.0'
        end

        template '/etc/nginx/nginx.conf' do
          source 'nginx.conf.erb'
          owner 'root'
          group 'root'
          mode '0644'
          notifies :restart, 'service[nginx]', :delayed
        end

        service 'nginx' do
          action [:enable, :start]
        end
        """
        
        result = parser._extract_resources(recipe_content)
        
        assert result is not None
        assert len(result) == 3
        assert result[0]['type'] == 'package'
        assert result[0]['name'] == 'nginx'
        assert 'action' in result[0]['properties']
        assert result[1]['type'] == 'template'
        assert result[1]['name'] == '/etc/nginx/nginx.conf'
        assert 'source' in result[1]['properties']
        assert result[2]['type'] == 'service'
        assert result[2]['name'] == 'nginx'
    
    def test_parse_attributes(self):
        """Test parsing attribute files"""
        parser = ChefParser()
        
        attr_content = """
        default['nginx']['version'] = '1.18.0'
        default['nginx']['user'] = 'www-data'
        default['nginx']['port'] = 80
        """
        
        # Mock Path.exists and Path.glob
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.glob") as mock_glob:
                mock_glob.return_value = [Path("attributes/default.rb")]
                
                # Mock open to return our test attributes
                with patch("builtins.open", mock_open(read_data=attr_content)):
                    result = parser._parse_attributes(Path("attributes"))
                    
                    assert result is not None
                    assert len(result) == 1
                    assert "name" in result[0]
                    assert "content" in result[0]
                    assert result[0]["name"] == "default"
                    assert "nginx" in result[0]["content"]
    
    def test_find_files(self):
        """Test finding static files"""
        parser = ChefParser()
        
        # Mock Path.exists and Path.glob
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.glob") as mock_glob:
                # Mock file paths
                mock_file1 = MagicMock()
                mock_file1.is_file.return_value = True
                mock_file1.name = "nginx.conf"
                mock_file1.relative_to.return_value = Path("default/nginx.conf")
                
                mock_file2 = MagicMock()
                mock_file2.is_file.return_value = True
                mock_file2.name = "vhost.conf"
                mock_file2.relative_to.return_value = Path("default/vhost.conf")
                
                mock_glob.return_value = [mock_file1, mock_file2]
                
                result = parser._find_files(Path("files"))
                
                assert result is not None
                assert len(result) == 2
                assert result[0]["name"] == "nginx.conf"
                assert result[1]["name"] == "vhost.conf"
    
    def test_parse_resources(self):
        """Test parsing custom resource files"""
        parser = ChefParser()
        
        resource_content = """
        property :name, String, name_property: true
        property :config_file, String, required: true
        
        action :create do
          template new_resource.config_file do
            source 'custom_template.erb'
            variables(name: new_resource.name)
          end
        end
        """
        
        # Mock Path.exists and Path.glob
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.glob") as mock_glob:
                mock_glob.return_value = [Path("resources/custom.rb")]
                
                # Mock open to return our test resource
                with patch("builtins.open", mock_open(read_data=resource_content)):
                    result = parser._parse_resources(Path("resources"))
                    
                    assert result is not None
                    assert len(result) == 1
                    assert "name" in result[0]
                    assert "content" in result[0]
                    assert result[0]["name"] == "custom"
                    assert "property" in result[0]["content"]
                    assert "action" in result[0]["content"]
    
    def test_parse_libraries(self):
        """Test parsing library files"""
        parser = ChefParser()
        
        library_content = """
        module MyHelpers
          def format_config(config)
            # Format the config
            config.to_json
          end
        end
        
        Chef::Recipe.include MyHelpers
        """
        
        # Mock Path.exists and Path.glob
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.glob") as mock_glob:
                mock_glob.return_value = [Path("libraries/helpers.rb")]
                
                # Mock open to return our test library
                with patch("builtins.open", mock_open(read_data=library_content)):
                    result = parser._parse_libraries(Path("libraries"))
                    
                    assert result is not None
                    assert len(result) == 1
                    assert "name" in result[0]
                    assert "content" in result[0]
                    assert result[0]["name"] == "helpers"
                    assert "module" in result[0]["content"]
    
    def test_find_data_bags(self):
        """Test finding data bags"""
        parser = ChefParser()
        
        data_bag_content = '{"id": "user1", "username": "john", "password": "secret"}'
        
        # Mock Path.exists and Path.glob for data_bags directory
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.glob") as mock_glob_dirs:
                # Mock data bag directories
                mock_dir = MagicMock()
                mock_dir.is_dir.return_value = True
                mock_dir.name = "users"
                mock_glob_dirs.return_value = [mock_dir]
                
                # Mock Path.glob for data bag items
                with patch.object(mock_dir, "glob") as mock_glob_items:
                    mock_glob_items.return_value = [Path("data_bags/users/user1.json")]
                    
                    # Mock open and json.load
                    with patch("builtins.open", mock_open(read_data=data_bag_content)):
                        with patch("json.load", return_value={"id": "user1", "username": "john", "password": "secret"}):
                            result = parser._find_data_bags(Path("data_bags"))
                            
                            assert result is not None
                            assert len(result) == 1
                            assert result[0]["name"] == "users"
                            assert "items" in result[0]
                            assert len(result[0]["items"]) == 1
                            assert result[0]["items"][0]["name"] == "user1"
