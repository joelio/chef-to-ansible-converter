"""
Fix for AnsibleGenerator to handle variables properly
"""

import re
import json
import os
from pathlib import Path

def extract_task_variables(tasks):
    """
    Extract variable names from Ansible tasks
    
    Args:
        tasks (list): List of Ansible tasks
        
    Returns:
        set: Set of variable names
    """
    # Convert tasks to string for regex
    tasks_str = json.dumps(tasks)
    
    # Find all {{ variable }} patterns
    pattern = r'{{\s*([a-zA-Z0-9_]+)\s*}}'
    matches = re.findall(pattern, tasks_str)
    
    # Filter out Ansible built-in variables
    ansible_vars = {'ansible_check_mode', 'ansible_facts'}
    return {var for var in matches if var not in ansible_vars}

def ensure_variables_defined(ansible_data, defaults_file):
    """
    Ensure all variables used in tasks are defined in defaults
    
    Args:
        ansible_data (dict): Ansible data with tasks and handlers
        defaults_file (Path): Path to defaults/main.yml
    """
    # Read existing defaults
    if defaults_file.exists():
        with open(defaults_file, 'r') as f:
            content = f.read()
            
        # Parse YAML content
        import yaml
        try:
            default_vars = yaml.safe_load(content) or {}
        except:
            default_vars = {}
    else:
        default_vars = {}
    
    # Extract variables from tasks and handlers
    all_vars = set()
    if 'tasks' in ansible_data and ansible_data['tasks']:
        all_vars.update(extract_task_variables(ansible_data['tasks']))
    
    if 'handlers' in ansible_data and ansible_data['handlers']:
        all_vars.update(extract_task_variables(ansible_data['handlers']))
    
    # Add missing variables with sensible defaults
    updated = False
    for var_name in all_vars:
        if var_name not in default_vars:
            updated = True
            # Common nginx variables
            if var_name == 'nginx_dir':
                default_vars[var_name] = '/etc/nginx'
            elif var_name == 'nginx_user':
                default_vars[var_name] = 'nginx'
            elif var_name == 'nginx_root':
                default_vars[var_name] = '/var/www/html'
            elif var_name == 'nginx_conf_d':
                default_vars[var_name] = '{{ nginx_dir }}/conf.d'
            elif var_name == 'application_dir':
                default_vars[var_name] = '{{ nginx_root }}/application'
            else:
                default_vars[var_name] = f"CHANGEME_{var_name}"
    
    # Write updated defaults if changes were made
    if updated:
        defaults_file.parent.mkdir(parents=True, exist_ok=True)
        with open(defaults_file, 'w') as f:
            yaml.dump(default_vars, f, default_flow_style=False)
        
        print(f"Updated defaults file with missing variables: {defaults_file}")
