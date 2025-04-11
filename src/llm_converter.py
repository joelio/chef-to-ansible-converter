"""
LLM converter module for the Chef to Ansible converter
"""

import os
import json
from pathlib import Path
import anthropic

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
        # In a real implementation, these would be loaded from a file or database
        # For now, we'll hardcode a few examples
        return [
            {
                "chef_code": """
package 'nginx' do
  action :install
end
                """,
                "ansible_code": """
- name: Install nginx
  package:
    name: nginx
    state: present
                """
            },
            {
                "chef_code": """
template '/etc/nginx/nginx.conf' do
  source 'nginx.conf.erb'
  variables(
    server_name: node['nginx']['server_name']
  )
  notifies :reload, 'service[nginx]'
end
                """,
                "ansible_code": """
- name: Configure nginx
  template:
    src: nginx.conf.j2
    dest: /etc/nginx/nginx.conf
  vars:
    server_name: "{{ nginx_server_name }}"
  notify: Reload nginx

# In handlers section:
- name: Reload nginx
  service:
    name: nginx
    state: reloaded
                """
            },
            {
                "chef_code": """
if platform_family?('debian')
  package 'apt-transport-https'
end
                """,
                "ansible_code": """
- name: Install apt-transport-https
  package:
    name: apt-transport-https
    state: present
  when: ansible_facts['os_family'] == 'Debian'
                """
            },
            {
                "chef_code": """
service 'nginx' do
  action [:enable, :start]
end
                """,
                "ansible_code": """
- name: Enable and start nginx service
  service:
    name: nginx
    state: started
    enabled: yes
                """
            },
            {
                "chef_code": """
directory '/var/www/html' do
  owner 'www-data'
  group 'www-data'
  mode '0755'
  recursive true
  action :create
end
                """,
                "ansible_code": """
- name: Create web directory
  file:
    path: /var/www/html
    state: directory
    owner: www-data
    group: www-data
    mode: '0755'
    recurse: yes
                """
            }
        ]
    
    def convert_cookbook(self, cookbook):
        """
        Convert a Chef cookbook to Ansible
        
        Args:
            cookbook (dict): Parsed cookbook
            
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
            
            conversion_result = self.convert_recipe(recipe)
            
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
    
    def convert_recipe(self, recipe):
        """
        Convert a Chef recipe to Ansible tasks
        
        Args:
            recipe (dict): Parsed recipe data
            
        Returns:
            dict: Converted Ansible tasks and handlers
        """
        # Build the prompt for the LLM
        prompt = self._build_conversion_prompt(recipe)
        
        # Call the Anthropic API
        response = self._call_anthropic_api(prompt)
        
        # Extract Ansible tasks and handlers from the response
        return self._extract_ansible_code(response)
    
    def _build_conversion_prompt(self, recipe):
        """
        Build a prompt for the LLM to convert a Chef recipe to Ansible
        
        Args:
            recipe (dict): Parsed recipe data
            
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

Here are some examples of Chef code and their Ansible equivalents:

{examples_text}

Now, please convert the following Chef recipe to Ansible, clearly separating tasks and handlers:

CHEF CODE:
```ruby
{recipe['content']}
```

Please provide the output in two separate YAML blocks: one for tasks and one for handlers.

For the handlers section, ONLY include handlers that are referenced by 'notifies' in the Chef recipe. Do NOT duplicate the tasks in the handlers section.

Format your response like this:

# Tasks
```yaml
- name: Task 1
  module:
    param: value
```

# Handlers
```yaml
- name: Handler 1
  module:
    param: value
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
                print("API call successful")
            
            # Send progress update
            if self.progress_callback:
                self.progress_callback({
                    'status': 'processing',
                    'message': "API call successful. Processing response...",
                    'progress': 75
                })
                
            return message.content[0].text
        except Exception as e:
            print(f"API Error: {str(e)}")
            
            # Send error update
            if self.progress_callback:
                self.progress_callback({
                    'status': 'error',
                    'message': f"API Error: {str(e)}",
                    'progress': 0
                })
                
            raise RuntimeError(f"Error calling Anthropic API: {str(e)}")
    
    def _extract_ansible_code(self, response):
        """
        Extract Ansible tasks and handlers from the LLM response
        
        Args:
            response (str): Response from the LLM
            
        Returns:
            dict: Extracted tasks and handlers
        """
        # Initialize result
        result = {
            'tasks': [],
            'handlers': []
        }
        
        # Look for sections labeled as tasks and handlers
        tasks_section = self._extract_section(response, "Tasks")
        handlers_section = self._extract_section(response, "Handlers")
        
        if tasks_section:
            result['tasks'] = self._parse_yaml_content(tasks_section)
        
        if handlers_section:
            result['handlers'] = self._parse_yaml_content(handlers_section)
        
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
            print(f"Extracted {len(result['tasks'])} tasks and {len(result['handlers'])} handlers")
        
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
        import yaml
        
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
        except Exception:
            # If parsing fails, return empty list
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
                
                # Determine the new path (change .erb to .j2)
                new_path = original_path
                if original_path.endswith('.erb'):
                    new_path = original_path[:-4] + '.j2'
                elif not original_path.endswith('.j2'):
                    new_path = original_path + '.j2'
                
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
