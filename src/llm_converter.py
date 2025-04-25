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
from src.resource_mapping import ResourceMapping

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
        
        # Load custom resource mappings
        self.custom_mappings = self._load_custom_mappings()
        
        # Initialize resource mapping
        custom_mapping_path = getattr(config, 'resource_mapping_path', None)
        self.resource_mapper = ResourceMapping(custom_mapping_path)
    
    def _load_custom_mappings(self):
        """Loads custom resource mappings from the JSON file specified in the config."""
        mapping_path = getattr(self.config, 'resource_mapping_path', None)
        if not mapping_path or not os.path.exists(mapping_path):
            return {}
        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading custom resource mappings: {e}")
            return {}
    
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
        
        # Build the prompt in sections for better maintainability using XML tags for structure
        intro = """
<role>
You are a Chef-to-Ansible migration specialist with expertise in both configuration management systems. Your primary responsibility is to convert Chef recipes into idiomatic, best-practice Ansible code that maintains the original functionality while leveraging Ansible's strengths.
</role>

<task>
Analyze the provided Chef recipe and convert it to equivalent Ansible code following a systematic approach:
1. First, understand what the Chef recipe is doing at a conceptual level
2. Identify all resources, variables, conditionals, and notifications in the Chef code
3. Map each Chef resource to its Ansible equivalent using best practices
4. Structure the Ansible code with proper task organization and variable separation
5. Verify the conversion maintains the same functionality as the original Chef code
</task>
"""

        best_practices = """
<guidelines:best_practices>
Follow these Ansible best practices in your conversion:
1. Always use Fully Qualified Collection Names (FQCN) for modules (e.g., 'ansible.builtin.template' instead of 'template')
2. Create descriptive task names that explain what the task is doing and why, not just the action
3. Always include explicit state parameters in modules (e.g., state: present, state: started)
4. Use 'true' and 'false' for boolean values, not 'yes' and 'no'
5. NEVER use reserved variable names like 'name', 'and', 'or', 'not', etc.
6. Use proper indentation and formatting in YAML (2 spaces for indentation)
7. Add appropriate tags to tasks for selective execution
8. Group related tasks using blocks for better organization and error handling
9. Ensure tasks are truly idempotent
10. Minimize use of shell/command modules when dedicated modules exist
</guidelines:best_practices>
"""

        variable_handling = """
<guidelines:variables>
VARIABLE HANDLING REQUIREMENTS:
1. ALWAYS define ALL variables used in tasks and templates in the Variables section
2. For Chef node attributes like 'node[:nginx][:dir]', create corresponding Ansible variables (e.g., nginx_dir)
3. Organize variables logically with comments explaining their purpose
4. Use snake_case for all variable names (e.g., nginx_user not nginxUser)
5. Separate variables between defaults (configurable) and vars (internal):
   - Place variables derived from Chef attributes or intended for user configuration in defaults/main.yml
   - Place internal role variables in vars/main.yml
6. NEVER hardcode version numbers or make assumptions about software versions
7. If the recipe includes 'include_attribute' statements, define those external variables
8. Use Ansible facts for system-related variables with sensible defaults
9. Include descriptive comments for complex variables or data structures
10. SCAN ALL templates for variables (enclosed in <%= %> or {{ }}) and define ALL of them
11. When handling nested dictionaries and complex data structures:
    - Initialize complex structures with empty defaults
    - Check if dictionaries exist before using filters like dict2items
    - Use the default filter when accessing potentially undefined dictionaries
</guidelines:variables>
"""

        directory_handling = """
<guidelines:directories>
DIRECTORY CREATION REQUIREMENTS:
1. ALWAYS create parent directories before creating files in them
2. Make your roles self-sufficient - never assume directories exist
3. Use the ansible.builtin.file module with state: directory to create directories
4. Set appropriate permissions on created directories
</guidelines:directories>
"""

        error_handling = """
<guidelines:error_handling>
ERROR HANDLING REQUIREMENTS:
1. Make your Ansible roles robust by including appropriate error handling
2. Use ignore_errors, failed_when, and changed_when as appropriate
3. Register command outputs and check return codes for failure conditions
4. For file operations, always check if files exist before modifying them
5. Use block/rescue/always structures for critical tasks to handle failures gracefully
6. Add retry logic for network or service operations using until/retries/delay
</guidelines:error_handling>
"""

        resource_mapping = """
<guidelines:resource_mapping>
CHEF-TO-ANSIBLE RESOURCE MAPPING:
1. Convert Chef resources to their Ansible module equivalents
2. For Chef 'notifies' actions:
   - Chef immediate notification (:immediately) → Ansible flush_handlers
   - Chef delayed notification (:delayed) → Ansible normal notification
3. For Chef guard properties:
   - Chef 'only_if' → Ansible 'when' condition
   - Chef 'not_if' → Ansible 'when: not' condition
4. For Chef attributes:
   - Chef 'node[...]' attributes → Ansible variables
   - Chef 'data_bag_item' → Ansible variables or ansible.builtin.include_vars
5. For custom resources (not in standard Chef resource set):
   - Create a placeholder task with name: "TODO: Convert Chef custom resource '[resource_name]'"
   - Include as much information about the resource as possible in the task vars
</guidelines:resource_mapping>
"""

        chain_of_thought = """
<thinking_process>
When converting Chef to Ansible, follow this step-by-step reasoning process:

1. ANALYSIS: First, analyze the Chef recipe to understand its overall purpose and components:
   - What resources are being managed? (packages, files, services, etc.)
   - What variables or attributes are being used?
   - What conditional logic exists?
   - What notifications or dependencies exist between resources?

2. MAPPING: For each Chef resource, determine the equivalent Ansible module:
   - Map each Chef resource type to the appropriate Ansible module
   - Translate Chef resource properties to Ansible module parameters
   - Convert Chef Ruby syntax to Ansible YAML syntax

3. VARIABLES: Identify all variables that need to be defined:
   - Convert Chef node attributes to Ansible variables
   - Determine which variables should be in defaults vs. vars
   - Create appropriate default values for variables

4. STRUCTURE: Organize the Ansible tasks in a logical sequence:
   - Group related tasks using blocks
   - Ensure prerequisites (users, directories) are created first
   - Convert Chef notifications to Ansible handlers

5. VERIFICATION: Verify the conversion is complete and correct:
   - Ensure all Chef resources have been converted
   - Check that all variables are defined
   - Verify that conditional logic works as expected
   - Confirm that notifications are properly implemented
</thinking_process>
"""

        output_format = f"""
<input>
Recipe Path: {recipe.get('path', 'Unknown')}

CHEF CODE:
```ruby
{recipe.get('content', 'No recipe content provided')}
```

{self._get_feedback_text(feedback)}
</input>

<output_format>
NOW, CONVERT THE FOLLOWING CHEF RECIPE:

Provide your response in the following format:

# Tasks
```yaml
# Your tasks here
```

# Handlers
```yaml
# Your handlers here
```

# Variables
```yaml
# Variables for defaults/main.yml (user-configurable)
# Your default variables here

# Variables for vars/main.yml (internal)
# Your internal variables here
```
</output_format>
"""
        
        # Combine all sections
        prompt = (
            intro +
            best_practices +
            variable_handling +
            directory_handling +
            error_handling +
            resource_mapping +
            chain_of_thought +
            "\nHERE ARE EXAMPLES:\n" + examples_text +
            output_format
        )
        
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
        
        # Post-process the result to handle custom resources
        result = self._post_process_custom_resources(result)
        
        return result
        
    def _post_process_custom_resources(self, result):
        """
        Post-process the conversion result to handle custom resources
        
        Args:
            result (dict): Conversion result with tasks, handlers, and variables
            
        Returns:
            dict: Updated conversion result with custom resources handled
        """
        # Process tasks for custom resources
        processed_tasks = []
        custom_resource_count = 0
        
        for task in result['tasks']:
            # Check if this is a placeholder for a custom resource
            if self._is_custom_resource_placeholder(task):
                custom_resource_count += 1
                resource_type = self._extract_resource_type(task)
                resource_data = self._extract_resource_data(task)
                
                # Try to handle the custom resource
                custom_tasks = self._handle_custom_resource(resource_type, resource_data)
                if custom_tasks:
                    processed_tasks.extend(custom_tasks)
                else:
                    # Keep the original task if we couldn't handle it
                    processed_tasks.append(task)
            else:
                processed_tasks.append(task)
        
        # Update the result with processed tasks
        result['tasks'] = processed_tasks
        
        if custom_resource_count > 0 and self.config.verbose and hasattr(self.config, 'verbose'):
            logger.info(f"Processed {custom_resource_count} custom resources")
        
        return result
    
    def _is_custom_resource_placeholder(self, task):
        """
        Check if a task is a placeholder for a custom resource
        
        Args:
            task (dict): Task to check
            
        Returns:
            bool: True if the task is a custom resource placeholder
        """
        # Check for common patterns in task names that indicate custom resources
        name = task.get('name', '')
        
        patterns = [
            r"TODO: Convert Chef custom resource '([^']+)'",
            r"Chef custom resource '([^']+)' requires manual conversion",
            r"Converted from Chef custom resource '([^']+)'",
            r"Unable to convert Chef resource '([^']+)'"
        ]
        
        for pattern in patterns:
            if re.search(pattern, name):
                return True
        
        # Check for debug module with custom resource message
        if 'ansible.builtin.debug' in task and 'msg' in task['ansible.builtin.debug']:
            msg = task['ansible.builtin.debug']['msg']
            if 'custom resource' in msg.lower() or 'requires manual conversion' in msg.lower():
                return True
        
        return False
    
    def _extract_resource_type(self, task):
        """
        Extract the resource type from a custom resource placeholder task
        
        Args:
            task (dict): Custom resource placeholder task
            
        Returns:
            str: Resource type or empty string if not found
        """
        name = task.get('name', '')
        
        # Try to extract from task name
        patterns = [
            r"TODO: Convert Chef custom resource '([^']+)'",
            r"Chef custom resource '([^']+)' requires manual conversion",
            r"Converted from Chef custom resource '([^']+)'",
            r"Unable to convert Chef resource '([^']+)'"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, name)
            if match:
                return match.group(1)
        
        # Try to extract from debug message
        if 'ansible.builtin.debug' in task and 'msg' in task['ansible.builtin.debug']:
            msg = task['ansible.builtin.debug']['msg']
            for pattern in patterns:
                match = re.search(pattern, msg)
                if match:
                    return match.group(1)
        
        # If we can't extract it, use a generic name
        return 'custom_resource'
    
    def _extract_resource_data(self, task):
        """
        Extract resource data from a custom resource placeholder task
        
        Args:
            task (dict): Custom resource placeholder task
            
        Returns:
            dict: Resource data extracted from the task
        """
        # Start with a basic resource data structure
        resource_data = {}
        
        # Look for resource data in task vars
        if 'vars' in task:
            resource_data.update(task['vars'])
        
        # Look for resource data in task parameters
        for key, value in task.items():
            if key not in ['name', 'ansible.builtin.debug', 'vars']:
                resource_data[key] = value
        
        return resource_data
    
    def _handle_custom_resource(self, resource_type, resource_data):
        """
        Handle a custom resource using the resource mapping system
        
        Args:
            resource_type (str): Type of the custom resource
            resource_data (dict): Data for the custom resource
            
        Returns:
            list: List of Ansible tasks that replace the custom resource
        """
        try:
            # Try to transform the resource using our mapping system
            return self.resource_mapper.transform_resource(resource_type, resource_data)
        except Exception as e:
            logger.warning(f"Error handling custom resource '{resource_type}': {str(e)}")
            # Return a commented task as a placeholder
            return [{
                "name": f"TODO: Convert Chef custom resource '{resource_type}' (mapping failed: {str(e)})",
                "ansible.builtin.debug": {
                    "msg": f"Chef custom resource '{resource_type}' requires manual conversion"
                }
            }]
    
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
