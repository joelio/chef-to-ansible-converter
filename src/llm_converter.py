"""
LLM converter module for the Chef to Ansible converter
"""

import os
import json
import re
import sys
from pathlib import Path

import anthropic
import yaml
from ruamel.yaml import YAML

from src.logger import logger

class LLMConverter:
    """Converts Chef code to Ansible using Anthropic's Claude API"""
    
    def __init__(self, config, progress_callback=None):
        """
        Initialize the LLM converter
        
        Args:
            config (Config): Configuration object
            progress_callback (callable): Optional callback function for progress updates
        """
        self.config = config
        self.client = anthropic.Anthropic(api_key=config.api_key)
        self.progress_callback = progress_callback
        
        # Load conversion examples
        self.examples = self._load_examples()
    
    def _load_examples(self):
        """
        Load Chef to Ansible conversion examples
        
        Returns:
            list: List of conversion examples
        """
        # These examples follow Ansible best practices:
        # 1. Use Fully Qualified Collection Names (FQCN) for modules
        # 2. Use proper capitalization for handler names
        # 3. Use 'true' and 'false' instead of 'yes' and 'no'
        return [
            {
                "chef_code": "\npackage 'nginx' do\n  action :install\nend\n            ",
                "ansible_code": "\n- name: Install nginx\n  ansible.builtin.package:\n    name: nginx\n    state: present\n            "
            },
            {
                "chef_code": "\ntemplate '/etc/nginx/nginx.conf' do\n  source 'nginx.conf.erb'\n  variables(\n    server_name: node['nginx']['server_name']\n  )\n  notifies :reload, 'service[nginx]'\nend\n            ",
                "ansible_code": "\n- name: Configure nginx\n  ansible.builtin.template:\n    src: nginx.conf.j2\n    dest: /etc/nginx/nginx.conf\n  vars:\n    server_name: \"{{ nginx_server_name }}\"\n  notify: Reload nginx\n\n# In handlers section:\n- name: Reload nginx\n  ansible.builtin.service:\n    name: nginx\n    state: reloaded\n            "
            },
            {
                "chef_code": "\nif platform_family?('debian')\n  package 'apt-transport-https'\nend\n            ",
                "ansible_code": "\n- name: Install apt-transport-https\n  ansible.builtin.package:\n    name: apt-transport-https\n    state: present\n  when: ansible_facts['os_family'] == 'Debian'\n            "
            },
            {
                "chef_code": "\nservice 'nginx' do\n  action [:enable, :start]\nend\n            ",
                "ansible_code": "\n- name: Enable and start nginx service\n  ansible.builtin.service:\n    name: nginx\n    state: started\n    enabled: true\n            "
            },
            {
                "chef_code": "\ndirectory '/var/www/html' do\n  owner 'www-data'\n  group 'www-data'\n  mode '0755'\n  recursive true\n  action :create\nend\n            ",
                "ansible_code": "\n- name: Create web directory\n  ansible.builtin.file:\n    path: /var/www/html\n    state: directory\n    owner: www-data\n    group: www-data\n    mode: '0755'\n    recurse: true\n            "
            }
]
    def convert_cookbook(self, cookbook, feedback=None):
        """
        Convert a Chef cookbook to Ansible
        
        Args:
            cookbook (dict): Parsed cookbook
            feedback (str): Feedback from previous conversion attempt
            
        Returns:
            dict: Converted Ansible code
        """
        # Initialize the result
        result = {
            'tasks': [],
            'handlers': [],
            'variables': {}
        }
        
        # Send progress update
        if self.progress_callback:
            self.progress_callback({
                'status': 'processing',
                'message': f"Starting conversion of cookbook: {cookbook.get('name', 'Unknown')}",
                'progress': 0
            })
        
        # Convert each recipe
        total_recipes = len(cookbook['recipes'])
        for i, recipe in enumerate(cookbook['recipes']):
            # Send progress update
            if self.progress_callback:
                self.progress_callback({
                    'status': 'processing',
                    'message': f"Converting recipe {i+1}/{total_recipes}: {recipe.get('name', 'Unknown')}",
                    'progress': (i / total_recipes) * 100
                })
            
            conversion_result = self.convert_recipe(recipe, feedback)
            
            # Add tasks and handlers from this recipe
            result['tasks'].extend(conversion_result.get('tasks', []))
            result['handlers'].extend(conversion_result.get('handlers', []))
            
            # Merge variables
            if 'variables' in conversion_result:
                result['variables'].update(conversion_result['variables'])
        
        # Send completion update
        if self.progress_callback:
            self.progress_callback({
                'status': 'completed',
                'message': f"Conversion complete. Generated {len(result['tasks'])} tasks and {len(result['handlers'])} handlers.",
                'progress': 100
            })
        
        return result
    
    def convert_recipe(self, recipe, feedback=None):
        """
        Convert a Chef recipe to Ansible tasks
        
        Args:
            recipe (dict): Parsed recipe data
            feedback (str): Feedback from previous conversion attempt
            
        Returns:
            dict: Converted Ansible tasks and handlers
        """
        # Build the prompt for the LLM
        prompt = self._build_conversion_prompt(recipe, feedback)
        
        # Call the Anthropic API
        response = self._call_anthropic_api(prompt)
        
        # Extract Ansible tasks and handlers from the response
        return self._extract_ansible_code(response)
    
    def _build_conversion_prompt(self, recipe, feedback=None):
        """
        Build a prompt for the LLM to convert a Chef recipe to Ansible
        
        Args:
            recipe (dict): Parsed recipe data
            feedback (str): Feedback from previous conversion attempt
            
        Returns:
            str: Prompt for the LLM
        """
        # Include a few examples for few-shot learning
        examples_text = ""
        for i, example in enumerate(self.examples[:self.config.examples_per_request]):
            examples_text += f"Example {i+1}:\n"
            examples_text += "CHEF CODE:\n```ruby\n" + example["chef_code"].strip() + "\n```\n\n"
            examples_text += "ANSIBLE CODE:\n```yaml\n" + example["ansible_code"].strip() + "\n```\n\n"
        
        # Build the main prompt
        prompt = f"""
You are an expert in both Chef and Ansible configuration management systems. Your task is to convert Chef code to equivalent Ansible code.

IMPORTANT: Follow these Ansible best practices in your conversion:
1. Always use Fully Qualified Collection Names (FQCN) for modules (e.g., 'ansible.builtin.template' instead of 'template')
2. Capitalize the first letter of all task and handler names (e.g., 'Restart nginx' not 'restart nginx')
3. Use 'true' and 'false' for boolean values, not 'yes' and 'no'
4. NEVER use reserved variable names like 'name', 'and', 'or', 'not', etc. Rename them (e.g., use 'hostname' instead of 'name')
5. Use proper indentation and formatting in YAML (2 spaces for indentation)
6. Use safe conditional checks in templates (e.g., '{{% if var is defined and var %}}')
7. Make handlers robust by adding ignore_errors: "{{{{ ansible_check_mode }}}}" for service restarts

CRITICAL VARIABLE HANDLING REQUIREMENTS:
1. ALWAYS define ALL variables used in tasks and templates in the Variables section
2. For Chef node attributes like 'node[:nginx][:dir]', create corresponding Ansible variables (e.g., nginx_dir)
3. ALWAYS include these common nginx variables if the recipe uses nginx:
   - nginx_dir: /etc/nginx
   - nginx_user: nginx
   - nginx_root: /var/www/html
   - nginx_conf_d: "{{ nginx_dir }}/conf.d"
   - nginx_version: "1.20.0"
   - nginx_log_dir: /var/log/nginx
   - nginx_error_log: "{{ nginx_log_dir }}/error.log"
   - nginx_access_log: "{{ nginx_log_dir }}/access.log"
4. If the recipe includes 'include_attribute' statements, you MUST define those external variables
5. ALWAYS define system-related variables and provide safe defaults for Ansible facts:
   - hostname: "{{ inventory_hostname }}"
   - fqdn: "{{ ansible_fqdn | default(inventory_hostname) }}"
   - domain: "{{ ansible_domain | default('example.com') }}"
   - ansible_default_ipv4: 
      address: "127.0.0.1"
   - ansible_hostname: "{{ inventory_hostname | default('localhost') }}"
   - ansible_os_family: "{{ ansible_os_family | default('RedHat') }}"
   
6. For cloud provider specific variables, include these defaults:
   - ec2:
       instance_id: "i-0123456789abcdef0"
       public_hostname: "ec2-example.compute.amazonaws.com"
       public_ipv4: "127.0.0.1"
       local_hostname: "ip-10-0-0-1.ec2.internal"
       local_ipv4: "10.0.0.1"
       placement_availability_zone: "us-east-1a"
   - ec2_instance_type: "t3.micro"
   - ec2_instance_id: "{{ ec2.instance_id | default('i-0123456789abcdef0') }}"
   - cloud_provider: "aws"
7. For platform-specific variables, provide sensible default values based on common configurations
8. NEVER leave undefined variables in tasks - ALL variables referenced in tasks must be defined
9. SCAN ALL templates for variables (enclosed in <%= %> or {{ }}) and define ALL of them
10. When handling nested dictionaries and complex data structures:
   - Always initialize complex structures with empty defaults
   - For example: nginx_example_remote_files_www: (empty dictionary)
   - Check if dictionaries exist before using filters like dict2items
   - Use the default filter when accessing potentially undefined dictionaries

DIRECTORY CREATION REQUIREMENTS:
1. ALWAYS create parent directories before creating files in them
2. For example, before creating /etc/nginx/conf.d/app.conf, first add a task to create /etc/nginx/conf.d
3. Make your roles self-sufficient - never assume directories exist
4. Use the ansible.builtin.file module with state: directory to create directories

USER HANDLING REQUIREMENTS:
1. NEVER assume users exist on the target system
2. Use variables for all users referenced in tasks (e.g., owner: "{{ nginx_user }}")
3. For setting ownership, prefer using variables over hardcoded user names
4. CRITICALLY IMPORTANT: The FIRST task in your role MUST create any users that will be referenced later
5. The complete order of operations for each role should be:
   a. First, create all required users
   b. Second, create all required directories
   c. Then create/modify files and set permissions
   d. Finally, start services or run commands
6. Example of proper user creation at the beginning of tasks:
   ```yaml
   - name: Create nginx user
     ansible.builtin.user:
       name: "{{ nginx_user }}"
       system: yes
     become: true
     ignore_errors: "{{ ansible_check_mode | default(false) }}"
   ```

TEMPLATE HANDLING REQUIREMENTS:
1. IMPORTANT: All ERB templates (.erb) are converted to Jinja2 templates (.j2)
2. When referencing templates in tasks, use the .j2 extension (e.g., 'application.conf.j2' not 'application.conf.erb')
3. In ansible.builtin.template module, use src: 'filename.j2' not the original ERB filename

SERVICE MANAGEMENT REQUIREMENTS:
1. For services managed by Chef notifies, use the appropriate Ansible handler and module
2. For handlers that restart services, add ignore_errors: true to prevent playbook failures
3. Use consistent service naming across all tasks
4. CRITICAL: Deduplicate handlers for the same service:
   - For the same service with the same action (restart/reload), create only ONE handler
   - If Chef has both immediate and delayed notifications, combine them into a single handler
   - Use distinct handler names for different actions on the same service (restart vs reload)
   - Never create multiple handlers with the same service and action but different names
5. Example service handler with proper error handling:
   ```yaml
   - name: Restart nginx
     ansible.builtin.service:
       name: nginx
       state: restarted
     become: true
     ignore_errors: true
     register: nginx_restart
     failed_when:
       - nginx_restart is failed
       - '"Could not find the requested service" not in nginx_restart.msg'
   ```

DEPENDENCY MANAGEMENT REQUIREMENTS:
1. Chef cookbooks often rely on external dependencies - create self-contained Ansible roles
2. If the Chef recipe installs packages, use ansible.builtin.package or the appropriate OS-specific module
3. Always check if packages are installed before using their services
4. For repository management:
   - For yum repositories, use ansible.builtin.yum_repository
   - For apt repositories, use ansible.builtin.apt_repository
   - Never use command modules to manage repositories when specific modules exist
5. For package caching:
   - Use ansible.builtin.yum with state: makecache instead of commands
   - Do not use warn parameter with command modules as it's deprecated
6. Example package installation with OS-specific handling:
   ```yaml
   - name: Install nginx package
     ansible.builtin.package:
       name: nginx
       state: present
     become: true
   ```

ERROR HANDLING REQUIREMENTS:
1. Make your Ansible roles robust by including appropriate error handling
2. Use ignore_errors, failed_when, and changed_when as appropriate
3. Register command outputs and check return codes for failure conditions
4. For file operations, always check if files exist before modifying them
5. Example robust command execution:
   ```yaml
   - name: Run a command
     ansible.builtin.command: /usr/bin/somecommand
     register: command_result
     failed_when: command_result.rc != 0 and command_result.rc != 2
     changed_when: command_result.rc == 0
     ignore_errors: "{{ ansible_check_mode | default(false) }}"
   ```

CONDITIONAL LOGIC REQUIREMENTS:
1. Convert Chef conditionals to Ansible conditionals using 'when:' statements
2. Handle platform-specific logic using ansible_facts variables
3. Chef 'only_if' and 'not_if' should be converted to appropriate 'when:' conditions
4. For complex conditions, use Ansible's and/or/not operators correctly
5. Example conversions:
   - Chef only_if condition → Ansible when condition
   - Chef not_if condition → Ansible when: not condition
   - Chef platform check → Ansible ansible_distribution check

PLATFORM-SPECIFIC HANDLING:
1. Convert Chef platform-specific code to Ansible distribution and OS family checks
2. Use ansible_distribution, ansible_os_family, and ansible_distribution_version facts
3. Handle different package managers based on OS family (apt vs yum vs dnf)
4. Create variables with OS-specific defaults that can be overridden
5. Example platform-specific package installation:
   ```yaml
   - name: Install required packages
     ansible.builtin.package:
       name: "{{ item }}"
       state: present
     loop: "{{ required_packages }}"
     vars:
       required_packages: "{{ debian_packages if ansible_os_family == 'Debian' else rhel_packages }}"
     when: not ansible_check_mode
   ```

RUBY-TO-YAML CONVERSION GUIDELINES:
1. Chef uses Ruby syntax, Ansible uses YAML - ensure proper translation
2. Convert Chef arrays to Ansible lists with proper YAML syntax
3. Convert Chef hashes to Ansible dictionaries with proper YAML syntax
4. Convert Chef blocks to Ansible task sequences
5. Convert Chef Ruby string interpolation to Ansible Jinja2 variables
6. Convert Chef Ruby conditionals to Ansible when statements
7. Ensure proper indentation in YAML output
8. When converting nested Chef node attributes to Ansible variables:
   - Chef: node['nginx']['sites']['default']['root'] = '/var/www/html'
   - Ansible: nginx_sites_default_root: '/var/www/html'
   - Always initialize nested dictionaries with empty values where needed: nginx_sites: (empty dictionary)

CHEF-TO-ANSIBLE RESOURCE MAPPING:
1. Convert Chef resources to their Ansible module equivalents as follows:
   - Chef 'package' → ansible.builtin.package
   - Chef 'template' → ansible.builtin.template
   - Chef 'cookbook_file' → ansible.builtin.copy
   - Chef 'file' → ansible.builtin.file
   - Chef 'directory' → ansible.builtin.file with state: directory
   - Chef 'service' → ansible.builtin.service
   - Chef 'execute' → ansible.builtin.command or ansible.builtin.shell
     - For ansible.builtin.command, ONLY use supported parameters: 
       - cmd or free-form parameter (required)
       - chdir, creates, executable, removes, stdin
       - DO NOT use: warn (deprecated)
   - Chef 'remote_file' → ansible.builtin.get_url
   - Chef 'git' → ansible.builtin.git
   - Chef 'user' → ansible.builtin.user
   - Chef 'group' → ansible.builtin.group
   - Chef 'mount' → ansible.builtin.mount
   - Chef 'cron' → ansible.builtin.cron
   - Chef 'apt_repository' → ansible.builtin.apt_repository
   - Chef 'yum_repository' → ansible.builtin.yum_repository

2. For Chef 'notifies' actions:
   - Chef immediate notification (:immediately) → Ansible flush_handlers
   - Chef delayed notification (:delayed) → Ansible normal notification

3. For Chef guard properties:
   - Chef 'only_if' → Ansible 'when' condition
   - Chef 'not_if' → Ansible 'when: not' condition

4. For Chef attributes:
   - Chef 'node[...]' attributes → Ansible variables
   - Chef 'data_bag_item' → Ansible variables or ansible.builtin.include_vars

VERIFICATION REQUIREMENTS:
Before finalizing your response, you MUST verify that your Ansible conversion meets all requirements above by checking:

1. VALIDATE ALL TASKS:
   - Every task has a properly capitalized name that clearly describes its purpose
   - All module names use Fully Qualified Collection Names (FQCN)
   - Boolean values use 'true' and 'false', not 'yes' and 'no'
   - No tasks use removed/deprecated parameters
   - All required parameters for each module are specified
   - Task ordering follows logical progression (users first, then directories, etc.)

2. VALIDATE ALL VARIABLES:
   - Every variable referenced in tasks and templates is defined in the variables section
   - No reserved names are used (name, and, or, not, etc.)
   - Nested dictionaries are properly initialized
   - Default values are provided for all variables
   - Chef node attributes are correctly converted to Ansible variables

3. VALIDATE ALL HANDLERS:
   - Handlers exist for all notified services
   - No duplicate handlers for the same service and action
   - Handler names are properly capitalized
   - Handlers include proper error handling (ignore_errors where appropriate)

4. VALIDATE DIRECTORIES AND PERMISSIONS:
   - Parent directories are created before files that use them
   - User/group references use variables, not hardcoded values
   - Directory permissions are set appropriately

5. VERIFY TEMPLATE HANDLING:
   - Template references use .j2 extension, not .erb
   - Template variables are properly converted from ERB to Jinja2 syntax

YOU MUST CORRECT ANY ISSUES FOUND DURING VERIFICATION BEFORE PROVIDING YOUR FINAL ANSWER.

Now, please convert the following Chef recipe to Ansible, clearly separating tasks and handlers:

CHEF CODE:
```ruby
{recipe['content']}
```

{self._get_feedback_text(feedback)}

Please provide the output in three separate blocks: tasks, handlers, and variables.

For the handlers section, ONLY include handlers that are referenced by 'notifies' in the Chef recipe. Do NOT duplicate the tasks in the handlers section.

For the variables section, INCLUDE ALL variables used in the tasks and templates, even those that might come from external cookbooks.

Format your response like this:

# Tasks
```yaml
- name: Task 1
  ansible.builtin.module:
    param: value
```

# Handlers
```yaml
- name: Handler 1
  ansible.builtin.module:
    param: value
    ignore_errors: "{{ ansible_check_mode }}"
```

# Variables
```yaml
# Define all variables used in the tasks and templates
# Include variables for external dependencies

# Nginx variables
nginx_dir: /etc/nginx
nginx_user: nginx
nginx_root: /var/www/html
nginx_conf_d: "{{ nginx_dir }}/conf.d"

# Application variables
application_dir: "{{ nginx_root }}/application"

# Other variables used in tasks
some_other_var: default_value
```

ANSIBLE CODE:

"""
        
        return prompt
    def _call_anthropic_api(self, prompt):
        """
        Call the Anthropic API to convert Chef code to Ansible
        
        Args:
            prompt (str): Prompt to send to the API
            
        Returns:
            str: Response from the API
        """
        try:
            # Use the latest Claude 3 Sonnet model
            model = "claude-3-7-sonnet-20250219"
            
            if self.config.verbose:
                print(f"Calling Anthropic API with model: {model}...")
            
            # Send progress update
            if self.progress_callback:
                self.progress_callback({
                    'status': 'processing',
                    'message': f"Calling Anthropic API with model: {model}...",
                    'progress': 50
                })
                
            message = self.client.messages.create(
                model=model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            if self.config.verbose:
                logger.debug("API call successful")
            
            # Send progress update
            if self.progress_callback:
                self.progress_callback({
                    'status': 'processing',
                    'message': "API call successful. Processing response...",
                    'progress': 75
                })
                
            return message.content[0].text
        except Exception as e:
            logger.error(f"API Error: {str(e)}")
            
            # Send error update
            if self.progress_callback:
                self.progress_callback({
                    'status': 'error',
                    'message': f"API Error: {str(e)}",
                    'progress': 0
                })
                
            raise RuntimeError(f"Error calling Anthropic API: {str(e)}")
    
    def _get_feedback_text(self, feedback):
        """Format feedback text for inclusion in the prompt
        
        Args:
            feedback (str): Feedback from previous conversion attempt
            
        Returns:
            str: Formatted feedback text or empty string if no feedback
        """
        if not feedback:
            return ""
            
        return f"""FEEDBACK FROM PREVIOUS CONVERSION:
{feedback}

YOU MUST FIX ALL ISSUES MENTIONED IN THE FEEDBACK ABOVE! Particularly:
1. If any directories don't exist, add tasks to create them BEFORE using them
2. If any users don't exist, either create them or use variables that can be overridden
3. Fix any undefined variables by adding them to defaults/main.yml"""
    
    def _extract_ansible_code(self, response):
        """Extract Ansible code from the LLM response
        
        Args:
            response (str): LLM response
            
        Returns:
            dict: Extracted Ansible code
        """
        # Initialize result
        result = {
            'tasks': [],
            'handlers': [],
            'variables': {}
        }
        
        # Look for sections labeled as tasks, handlers, and variables
        tasks_section = self._extract_section(response, "Tasks")
        handlers_section = self._extract_section(response, "Handlers")
        variables_section = self._extract_section(response, "Variables")
        
        if tasks_section:
            result['tasks'] = self._parse_yaml_content(tasks_section)
        
        if handlers_section:
            result['handlers'] = self._parse_yaml_content(handlers_section)
            
        if variables_section:
            # Parse variables as a dictionary instead of a list
            try:
                variables_yaml = variables_section.strip()
                if variables_yaml:
                    # Remove comments from variables section
                    cleaned_variables = '\n'.join([line for line in variables_yaml.split('\n') 
                                                  if not line.strip().startswith('#')])
                    result['variables'] = yaml.safe_load(cleaned_variables) or {}
            except Exception as e:
                logger.warning(f"Error parsing response as YAML: {str(e)}")
                result['variables'] = {}
        
        # If no specific sections found, try to extract based on code blocks
        if not result['tasks'] and not result['handlers']:
            # Look for specific task and handler sections
            tasks_match = self._extract_code_block(response, "tasks.yml")
            handlers_match = self._extract_code_block(response, "handlers.yml")
            
            if tasks_match:
                result['tasks'] = self._parse_yaml_content(tasks_match)
            
            if handlers_match:
                result['handlers'] = self._parse_yaml_content(handlers_match)
        
        # If still no specific sections found, try to extract any YAML block
        if not result['tasks'] and not result['handlers']:
            yaml_blocks = self._extract_all_yaml_blocks(response)
            if yaml_blocks:
                # Assume first block is tasks, second is handlers if present
                result['tasks'] = self._parse_yaml_content(yaml_blocks[0])
                if len(yaml_blocks) > 1:
                    result['handlers'] = self._parse_yaml_content(yaml_blocks[1])
        
        # Log extraction results if verbose
        if self.config.verbose and hasattr(self.config, 'verbose'):
            logger.debug(f"Extracted {len(result['tasks'])} tasks and {len(result['handlers'])} handlers")
        
        return result
    
    def _extract_code_block(self, text, block_name):
        """
        Extract a specific code block from text
        
        Args:
            text (str): Text to extract from
            block_name (str): Name of the block to extract
            
        Returns:
            str: Extracted code block or None if not found
        """
        import re
        
        # Look for block with specific name
        pattern = rf"(?:```yaml|```yml)\s*(?:#\s*{block_name})?\s*(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        return None
    
    def _extract_all_yaml_blocks(self, text):
        """
        Extract all YAML code blocks from text
        
        Args:
            text (str): Text to extract from
            
        Returns:
            list: List of extracted YAML blocks
        """
        import re
        
        # Extract all YAML blocks
        pattern = r"```(?:yaml|yml)\s*(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        
        return [match.strip() for match in matches]
        
    def _extract_section(self, text, section_name):
        """
        Extract a section based on a header (e.g., '# Tasks' or '# Handlers')
        
        Args:
            text (str): Text to extract from
            section_name (str): Name of the section to extract
            
        Returns:
            str: Extracted section content or None if not found
        """
        import re
        
        # Look for section headers like '# Tasks' or '# Handlers'
        pattern = rf"#\s*{section_name}[^\n]*\n\s*```(?:yaml|yml)?\s*(.*?)```"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        
        if match:
            return match.group(1).strip()
            
        # Try alternative format without code blocks
        pattern = rf"#\s*{section_name}[^\n]*\n((?:[ \t]*-.*\n)+)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        
        if match:
            return match.group(1).strip()
            
        return None
    
    def _parse_yaml_content(self, yaml_content):
        """
        Parse YAML content to Python objects
        
        Args:
            yaml_content (str): YAML content to parse
            
        Returns:
            list: Parsed YAML content
        """
        try:
            # Try to parse the YAML content
            parsed = yaml.safe_load(yaml_content)
            
            # Ensure we return a list
            if parsed is None:
                return []
            elif isinstance(parsed, list):
                return parsed
            else:
                return [parsed]
        except yaml.YAMLError as e:
            logger.warning(f"YAML parsing failed: {e}")
            return []
        except Exception as e:
            # If parsing fails, return empty list
            logger.error(f"Error parsing YAML: {str(e)}")
            return []
    
    def convert_attributes(self, attributes):
        """
        Convert Chef attributes to Ansible variables
        
        Args:
            attributes (list): Parsed attribute files
            
        Returns:
            dict: Converted Ansible variables
        """
        # For now, we'll just return a placeholder
        # In a real implementation, this would parse Chef attributes and convert them to Ansible variables
        variables = {}
        
        for attr_file in attributes:
            # Build a prompt for the LLM to convert attributes
            prompt = f"""
Convert the following Chef attributes to Ansible variables:

```ruby
{attr_file['content']}
```

Please provide the equivalent Ansible variables in YAML format.
"""
            
            # Call the Anthropic API
            response = self._call_anthropic_api(prompt)
            
            # Extract YAML content
            yaml_block = self._extract_all_yaml_blocks(response)
            if yaml_block:
                # Parse YAML content
                parsed = self._parse_yaml_content(yaml_block[0])
                if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
                    variables.update(parsed[0])
                elif isinstance(parsed, dict):
                    variables.update(parsed)
        
        return variables
    
    def convert_templates(self, templates):
        """
        Convert Chef templates to Ansible templates
        
        Args:
            templates (list): Chef templates
            
        Returns:
            list: Converted Ansible templates
        """
        ansible_templates = []
        
        if not templates:
            # If no templates were provided, create a sample template to demonstrate structure
            print("No Chef templates found. Creating a sample template.")
            sample_template = {
                'name': 'sample',
                'path': 'sample.j2',
                'content': '# Sample Ansible template\n# This is a placeholder for demonstration purposes\n\n' +
                          '# Example of variable usage:\n{{ ansible_hostname }}\n{{ inventory_hostname }}\n\n' +
                          '# Example of conditional:\n{% if ansible_os_family == "Debian" %}\n' +
                          'This is a Debian-based system\n{% elif ansible_os_family == "RedHat" %}\n' +
                          'This is a RedHat-based system\n{% else %}\n' +
                          'This is another type of system\n{% endif %}'
            }
            return [sample_template]
        
        for template in templates:
            if not template or 'content' not in template or template['content'] is None:
                continue
                
            try:
                # Get the original path and name
                original_path = template.get('path', '')
                template_name = template.get('name', os.path.basename(original_path))
                
                # Convert ERB syntax to Jinja2
                converted_content = self._convert_erb_to_jinja(template['content'])
                
                # Determine the new path (change .erb to .j2 and remove 'default/' prefix)
                new_path = original_path
                
                # Remove 'default/' prefix if present (Chef-specific convention)
                if new_path.startswith('default/'):
                    new_path = new_path[8:]
                
                # Change file extension from .erb to .j2
                if new_path.endswith('.erb'):
                    new_path = new_path[:-4] + '.j2'
                elif not new_path.endswith('.j2'):
                    new_path = new_path + '.j2'
                
                # Add a header to the template explaining it was converted
                header = f"#\n# Ansible Template: {template_name}\n# Converted from Chef ERB template\n#\n\n"
                converted_content = header + converted_content
                
                ansible_templates.append({
                    'name': template_name,
                    'path': new_path,
                    'content': converted_content
                })
                
                print(f"Converted template: {template_name} -> {new_path}")
                
            except Exception as e:
                print(f"Error converting template {template.get('name', 'unknown')}: {str(e)}")
                # Still include the template, but with an error message
                ansible_templates.append({
                    'name': template.get('name', 'error_template'),
                    'path': template.get('path', 'error_template.j2').replace('.erb', '.j2'),
                    'content': f"# Error converting template\n# {str(e)}\n\n{template.get('content', '')}"  
                })
        
        return ansible_templates
    
    def _convert_erb_to_jinja(self, erb_content):
        """
        Convert ERB syntax to Jinja2
        
        Args:
            erb_content (str): ERB template content
            
        Returns:
            str: Jinja2 template content
        """
        if not erb_content:
            return ""
            
        import re
        
        # Store the conversion in a log for debugging
        conversion_log = ["ERB to Jinja2 conversion:"]
        conversion_log.append(f"Original ERB:\n{erb_content[:200]}...")
        
        # Step 1: Handle ERB output tags (<%= ... %>) - convert to Jinja2 {{ ... }}
        # But first, escape any existing {{ or }} in the content
        jinja_content = erb_content.replace('{{', r'\{\{').replace('}}', r'\}\}')
        jinja_content = re.sub(r'<%=\s*(.+?)\s*%>', r'{{ \1 }}', jinja_content)
        
        # Step 2: Handle ERB control flow tags (<% if ... %>, <% else %>, <% end %>, etc.)
        # Convert if statements
        jinja_content = re.sub(r'<%\s*if\s+(.+?)\s*%>', r'{% if \1 %}', jinja_content)
        jinja_content = re.sub(r'<%\s*elsif\s+(.+?)\s*%>', r'{% elif \1 %}', jinja_content)
        jinja_content = re.sub(r'<%\s*else\s*%>', r'{% else %}', jinja_content)
        
        # Convert loops
        jinja_content = re.sub(r'<%\s*(.+?)\.each\s+do\s*\|\s*(.+?)\s*\|\s*%>', r'{% for \2 in \1 %}', jinja_content)
        
        # Convert end tags
        jinja_content = re.sub(r'<%\s*end\s*%>', r'{% endfor %}', jinja_content)
        # Check if we have more end tags than for tags, if so, convert some to endif
        endfor_count = jinja_content.count('{% endfor %}')
        for_count = len(re.findall(r'{%\s*for\s+', jinja_content))
        if endfor_count > for_count:
            # Replace the extra endfor tags with endif
            jinja_content = jinja_content.replace('{% endfor %}', '{% endif %}', endfor_count - for_count)
        
        # Step 3: Convert remaining ERB tags (<% ... %>) to Jinja2 {% ... %}
        jinja_content = re.sub(r'<%\s*(.+?)\s*%>', r'{% \1 %}', jinja_content)
        
        # Step 4: Convert Chef node attributes to Ansible variables
        # node['attribute'] -> attribute
        # node['section']['attribute'] -> section_attribute
        # node[:attribute] -> attribute (Chef symbol syntax)
        # node.attribute -> attribute (Chef dot syntax)
        
        # Handle node['attr'] syntax
        jinja_content = re.sub(r"node\['([^']+)'\]\['([^']+)'\]\['([^']+)'\]", r"\1_\2_\3", jinja_content)
        jinja_content = re.sub(r"node\['([^']+)'\]\['([^']+)'\]", r"\1_\2", jinja_content)
        jinja_content = re.sub(r"node\['([^']+)'\]", r"\1", jinja_content)
        
        # Handle node[:attr] syntax
        jinja_content = re.sub(r"node\[:([^\]]+)\]\[:([^\]]+)\]\[:([^\]]+)\]", r"\1_\2_\3", jinja_content)
        jinja_content = re.sub(r"node\[:([^\]]+)\]\[:([^\]]+)\]", r"\1_\2", jinja_content)
        jinja_content = re.sub(r"node\[:([^\]]+)\]", r"\1", jinja_content)
        
        # Handle node.attr syntax
        jinja_content = re.sub(r"node\.([a-zA-Z0-9_]+)", r"\1", jinja_content)
        
        # Special case for common node attributes
        jinja_content = jinja_content.replace("hostname", "ansible_hostname")
        jinja_content = jinja_content.replace("ipaddress", "ansible_default_ipv4.address")
        jinja_content = jinja_content.replace("platform", "ansible_distribution")
        jinja_content = jinja_content.replace("platform_version", "ansible_distribution_version")
        
        # Step 5: Convert Chef-specific functions to Ansible equivalents
        # Chef's File.exist? -> Jinja2's is defined
        jinja_content = re.sub(r"File\.exist\?\(['\"](.*?)['\"]\)", r"'\1' is defined", jinja_content)
        
        # Step 6: Convert Ruby string interpolation to Jinja2
        # "#{variable}" -> "{{ variable }}"
        jinja_content = re.sub(r'"([^"]*?)#\{(.+?)\}([^"]*?)"', r'"\1{{ \2 }}\3"', jinja_content)
        
        # Log the conversion result
        conversion_log.append(f"Converted Jinja2:\n{jinja_content[:200]}...")
        print("\n".join(conversion_log))
        
        # Replace reserved variable names
        jinja_content = jinja_content.replace("{{ name }}", "{{ hostname }}")
        jinja_content = jinja_content.replace("{% if name", "{% if hostname")
        
        return jinja_content
    
    def convert_files(self, files):
        """
        Convert Chef files to Ansible files
        
        Args:
            files (list): Chef files
            
        Returns:
            list: Ansible files
        """
        # For static files, we can just copy them as-is
        return files
