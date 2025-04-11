"""
Chef parser module for the Chef to Ansible converter
"""

import os
import re
import json
from pathlib import Path

class ChefParser:
    """Parses Chef cookbooks and recipes"""
    
    def __init__(self):
        """Initialize the Chef parser"""
        pass
    
    def find_cookbooks(self, repo_path):
        """
        Find all cookbooks in a repository
        
        Args:
            repo_path (Path): Path to the repository
            
        Returns:
            list: List of dictionaries containing cookbook information
        """
        cookbooks = []
        
        # Look for metadata.rb files which indicate a cookbook
        for metadata_file in repo_path.glob('**/metadata.rb'):
            cookbook_path = metadata_file.parent
            cookbook_name = self._extract_cookbook_name(metadata_file)
            
            cookbooks.append({
                'name': cookbook_name,
                'path': cookbook_path
            })
        
        return cookbooks
    
    def _extract_cookbook_name(self, metadata_file):
        """
        Extract the cookbook name from metadata.rb
        
        Args:
            metadata_file (Path): Path to metadata.rb
            
        Returns:
            str: Cookbook name
        """
        with open(metadata_file, 'r') as f:
            content = f.read()
        
        # Look for name attribute in metadata.rb
        name_match = re.search(r'name\s+[\'"]([^\'"]+)[\'"]', content)
        if name_match:
            return name_match.group(1)
        
        # If name is not specified, use the directory name
        return metadata_file.parent.name
    
    def parse_cookbook(self, cookbook_path):
        """
        Parse a Chef cookbook
        
        Args:
            cookbook_path (Path): Path to the cookbook
            
        Returns:
            dict: Parsed cookbook data
        """
        cookbook_data = {
            'name': cookbook_path.name,
            'metadata': self._parse_metadata(cookbook_path / 'metadata.rb'),
            'recipes': self._parse_recipes(cookbook_path / 'recipes'),
            'attributes': self._parse_attributes(cookbook_path / 'attributes'),
            'templates': self._find_templates(cookbook_path / 'templates'),
            'files': self._find_files(cookbook_path / 'files'),
            'resources': self._parse_resources(cookbook_path / 'resources'),
            'libraries': self._parse_libraries(cookbook_path / 'libraries'),
            'data_bags': self._find_data_bags(cookbook_path.parent.parent / 'data_bags')
        }
        
        return cookbook_data
    
    def _parse_metadata(self, metadata_file):
        """
        Parse metadata.rb file
        
        Args:
            metadata_file (Path): Path to metadata.rb
            
        Returns:
            dict: Metadata information
        """
        if not metadata_file.exists():
            return {}
        
        with open(metadata_file, 'r') as f:
            content = f.read()
        
        metadata = {}
        
        # Extract common metadata attributes
        for attr in ['name', 'version', 'maintainer', 'maintainer_email', 'license', 'description']:
            match = re.search(rf'{attr}\s+[\'"]([^\'"]+)[\'"]', content)
            if match:
                metadata[attr] = match.group(1)
        
        # Extract dependencies
        dependencies = re.findall(r'depends\s+[\'"]([^\'"]+)[\'"](?:\s*,\s*[\'"]([^\'"]+)[\'"])?', content)
        metadata['dependencies'] = [{'name': dep[0], 'version': dep[1] if dep[1] else None} for dep in dependencies]
        
        return metadata
    
    def _parse_recipes(self, recipes_dir):
        """
        Parse recipe files in a cookbook
        
        Args:
            recipes_dir (Path): Path to the recipes directory
            
        Returns:
            list: List of parsed recipes
        """
        if not recipes_dir.exists():
            return []
        
        recipes = []
        
        for recipe_file in recipes_dir.glob('*.rb'):
            with open(recipe_file, 'r') as f:
                content = f.read()
            
            recipe_name = recipe_file.stem
            
            recipes.append({
                'name': recipe_name,
                'path': str(recipe_file),
                'content': content,
                'resources': self._extract_resources(content)
            })
        
        return recipes
    
    def _extract_resources(self, content):
        """
        Extract Chef resources from recipe content
        
        Args:
            content (str): Recipe content
            
        Returns:
            list: List of resources
        """
        resources = []
        
        # Common Chef resource types
        resource_types = [
            'package', 'service', 'template', 'cookbook_file', 'file', 'directory',
            'execute', 'bash', 'ruby_block', 'cron', 'user', 'group', 'mount',
            'remote_file', 'git', 'apt_repository', 'yum_repository', 'apt_update'
        ]
        
        # Pattern to match resource blocks
        resource_pattern = r'(%s)\s+[\'"]([^\'"]+)[\'"]\s+do\s+(.*?)\s+end' % '|'.join(resource_types)
        
        # Find all resource blocks using regex
        for match in re.finditer(resource_pattern, content, re.DOTALL):
            resource_type = match.group(1)
            resource_name = match.group(2)
            resource_content = match.group(3)
            
            # Extract properties from the resource block
            properties = {}
            for prop_match in re.finditer(r'(\w+)\s+(.+?)(?=\n\s+\w+\s+|\Z)', resource_content, re.DOTALL):
                prop_name = prop_match.group(1)
                prop_value = prop_match.group(2).strip()
                properties[prop_name] = prop_value
            
            resources.append({
                'type': resource_type,
                'name': resource_name,
                'properties': properties,
                'raw_content': match.group(0)
            })
        
        return resources
    
    def _parse_attributes(self, attributes_dir):
        """
        Parse attribute files in a cookbook
        
        Args:
            attributes_dir (Path): Path to the attributes directory
            
        Returns:
            list: List of parsed attribute files
        """
        if not attributes_dir.exists():
            return []
        
        attributes = []
        
        for attr_file in attributes_dir.glob('*.rb'):
            with open(attr_file, 'r') as f:
                content = f.read()
            
            attributes.append({
                'name': attr_file.stem,
                'path': str(attr_file),
                'content': content
            })
        
        return attributes
    
    def _find_templates(self, templates_dir):
        """
        Find template files in a cookbook
        
        Args:
            templates_dir (Path): Path to the templates directory
            
        Returns:
            list: List of template files
        """
        if not templates_dir.exists():
            return []
        
        templates = []
        
        for template_file in templates_dir.glob('**/*'):
            if template_file.is_file():
                with open(template_file, 'r', errors='ignore') as f:
                    try:
                        content = f.read()
                    except UnicodeDecodeError:
                        content = None
                
                templates.append({
                    'name': template_file.name,
                    'path': str(template_file.relative_to(templates_dir)),
                    'content': content
                })
        
        return templates
    
    def _find_files(self, files_dir):
        """
        Find static files in a cookbook
        
        Args:
            files_dir (Path): Path to the files directory
            
        Returns:
            list: List of static files
        """
        if not files_dir.exists():
            return []
        
        files = []
        
        for file_path in files_dir.glob('**/*'):
            if file_path.is_file():
                files.append({
                    'name': file_path.name,
                    'path': str(file_path.relative_to(files_dir))
                })
        
        return files
    
    def _parse_resources(self, resources_dir):
        """
        Parse custom resource files in a cookbook
        
        Args:
            resources_dir (Path): Path to the resources directory
            
        Returns:
            list: List of parsed custom resources
        """
        if not resources_dir.exists():
            return []
        
        resources = []
        
        for resource_file in resources_dir.glob('*.rb'):
            with open(resource_file, 'r') as f:
                content = f.read()
            
            resources.append({
                'name': resource_file.stem,
                'path': str(resource_file),
                'content': content
            })
        
        return resources
    
    def _parse_libraries(self, libraries_dir):
        """
        Parse library files in a cookbook
        
        Args:
            libraries_dir (Path): Path to the libraries directory
            
        Returns:
            list: List of parsed library files
        """
        if not libraries_dir.exists():
            return []
        
        libraries = []
        
        for library_file in libraries_dir.glob('*.rb'):
            with open(library_file, 'r') as f:
                content = f.read()
            
            libraries.append({
                'name': library_file.stem,
                'path': str(library_file),
                'content': content
            })
        
        return libraries
    
    def _find_data_bags(self, data_bags_dir):
        """
        Find data bags in a Chef repository
        
        Args:
            data_bags_dir (Path): Path to the data_bags directory
            
        Returns:
            list: List of data bags
        """
        if not data_bags_dir.exists():
            return []
        
        data_bags = []
        
        for bag_dir in data_bags_dir.glob('*'):
            if bag_dir.is_dir():
                items = []
                
                for item_file in bag_dir.glob('*.json'):
                    with open(item_file, 'r') as f:
                        try:
                            content = json.load(f)
                        except json.JSONDecodeError:
                            content = {}
                    
                    items.append({
                        'name': item_file.stem,
                        'content': content
                    })
                
                data_bags.append({
                    'name': bag_dir.name,
                    'items': items
                })
        
        return data_bags
