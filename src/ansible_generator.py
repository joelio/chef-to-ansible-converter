"""
Ansible generator module for the Chef to Ansible converter
"""

import os
import yaml
from pathlib import Path

class AnsibleGenerator:
    """Generates Ansible playbooks and roles from converted Chef code"""
    
    def __init__(self):
        """Initialize the Ansible generator"""
        # Use ruamel.yaml for better YAML formatting
        from ruamel.yaml import YAML
        self.yaml = YAML()
        self.yaml.indent(mapping=2, sequence=4, offset=2)
        self.yaml.preserve_quotes = True
    
    def generate_ansible_role(self, ansible_data, output_path):
        """
        Generate an Ansible role from converted Chef code
        
        Args:
            ansible_data (dict): Converted Ansible data
            output_path (str or Path): Path to output the Ansible role
        """
        # Create role directory structure
        role_path = Path(output_path) if isinstance(output_path, str) else output_path
        role_path.mkdir(parents=True, exist_ok=True)
        
        # Create directories
        for dir_name in ['tasks', 'handlers', 'templates', 'files', 'vars', 'defaults', 'meta']:
            (role_path / dir_name).mkdir(exist_ok=True)
        
        # Write tasks
        if ansible_data['tasks']:
            self._write_yaml_file(role_path / 'tasks' / 'main.yml', ansible_data['tasks'])
        
        # Write handlers
        if ansible_data['handlers']:
            self._write_yaml_file(role_path / 'handlers' / 'main.yml', ansible_data['handlers'])
        
        # Write variables
        if ansible_data['variables']:
            self._write_yaml_file(role_path / 'defaults' / 'main.yml', ansible_data['variables'])
        
        # Write templates
        if 'templates' in ansible_data and ansible_data['templates']:
            for template in ansible_data['templates']:
                # Make sure template has the required fields
                if 'path' not in template or 'content' not in template:
                    print(f"Warning: Template missing required fields: {template}")
                    continue
                    
                # Ensure template path is properly formatted
                # Create a Path object from the template path
                template_rel_path = Path(template['path'])
                
                # Create the full path in the role's templates directory
                template_path = role_path / 'templates' / template_rel_path
                template_path.parent.mkdir(parents=True, exist_ok=True)
                
                print(f"Creating template at: {template_path}")
                
                # Write template content
                try:
                    with open(template_path, 'w') as f:
                        f.write(template['content'])
                    print(f"Created template: {template_path}")
                except Exception as e:
                    print(f"Error creating template {template_path}: {str(e)}")
                    
            # Create a sample template if none were provided
            if not any(os.path.exists(role_path / 'templates' / template['path']) 
                      for template in ansible_data['templates'] if 'path' in template):
                sample_template_path = role_path / 'templates' / 'sample.j2'
                with open(sample_template_path, 'w') as f:
                    f.write("# Sample template for {{ role_name }}\n\n# This is a placeholder template file.\n")
                print(f"Created sample template: {sample_template_path}")
        
        # Write files
        if 'files' in ansible_data and ansible_data['files']:
            for file_data in ansible_data['files']:
                file_path = role_path / 'files' / file_data['path']
                file_path.parent.mkdir(parents=True, exist_ok=True)
                # In a real implementation, we would copy the file content
                # Here we just create an empty file as a placeholder
                file_path.touch()
        
        # Create meta/main.yml with role metadata
        # Get the cookbook name or use a default value if not present
        cookbook_name = ansible_data.get('name', os.path.basename(output_path))
        
        meta = {
            'galaxy_info': {
                'author': 'Chef to Ansible Converter',
                'description': f'Converted from Chef cookbook {cookbook_name}',
                'license': 'MIT',
                'min_ansible_version': '2.9',
                'platforms': [
                    {'name': 'EL', 'versions': ['7', '8']},
                    {'name': 'Ubuntu', 'versions': ['bionic', 'focal']},
                    {'name': 'Debian', 'versions': ['buster', 'bullseye']}
                ]
            },
            'dependencies': []
        }
        self._write_yaml_file(role_path / 'meta' / 'main.yml', meta)
        
        # Create README.md
        readme_content = f"""# {ansible_data['name']}

Ansible role converted from Chef cookbook {ansible_data['name']}.

## Requirements

Any pre-requisites that may not be covered by Ansible itself or the role should be mentioned here.

## Role Variables

A description of the settable variables for this role should go here, including any variables that are in defaults/main.yml, vars/main.yml, and any variables that can/should be set via parameters to the role.

## Dependencies

A list of other roles hosted on Galaxy should go here, plus any details in regards to parameters that may need to be set for other roles, or variables that are used from other roles.

## Example Playbook

```yaml
- hosts: servers
  roles:
     - role_name
```

## License

MIT

## Author Information

This role was converted from a Chef cookbook by the Chef to Ansible Converter.
"""
        with open(role_path / 'README.md', 'w') as f:
            f.write(readme_content)
    
    def _write_yaml_file(self, file_path, data):
        """
        Write data to a YAML file
        
        Args:
            file_path (Path): Path to the output file
            data: Data to write
        """
        with open(file_path, 'w') as f:
            self.yaml.dump(data, f)
