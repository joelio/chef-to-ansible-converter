#!/usr/bin/env python3
"""
Demo script for the Chef to Ansible converter
"""

import os
import sys
import argparse
from pathlib import Path
import yaml

from src.config import Config
from src.llm_converter import LLMConverter

def main():
    parser = argparse.ArgumentParser(description='Demo Chef to Ansible conversion')
    parser.add_argument('--api-key', default=os.environ.get('ANTHROPIC_API_KEY'), 
                        help='Anthropic API key (default: ANTHROPIC_API_KEY env var)')
    parser.add_argument('--model', default='claude-3-opus-20240229',
                        help='Anthropic model to use (default: claude-3-opus-20240229)')
    parser.add_argument('--chef-file', default='examples/nginx_chef.rb',
                        help='Path to Chef recipe file (default: examples/nginx_chef.rb)')
    parser.add_argument('--output-file', default='examples/converted_ansible.yml',
                        help='Path to output Ansible file (default: examples/converted_ansible.yml)')
    
    args = parser.parse_args()
    
    if not args.api_key:
        print("Error: Anthropic API key is required. Set it with --api-key or ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)
    
    # Read Chef recipe
    chef_file = Path(args.chef_file)
    if not chef_file.exists():
        print(f"Error: Chef file {args.chef_file} not found.")
        sys.exit(1)
    
    with open(chef_file, 'r') as f:
        chef_content = f.read()
    
    # Create mock recipe data
    recipe = {
        'name': chef_file.stem,
        'path': str(chef_file),
        'content': chef_content,
        'resources': []  # We don't need to parse resources for the demo
    }
    
    # Initialize converter
    config = Config(api_key=args.api_key, model=args.model, verbose=True)
    converter = LLMConverter(config)
    
    print(f"Converting Chef recipe {args.chef_file}...")
    
    # Convert recipe
    try:
        result = converter.convert_recipe(recipe)
        
        # Write tasks to output file
        output_file = Path(args.output_file)
        
        # Create a nicer YAML dump
        from ruamel.yaml import YAML
        yaml_writer = YAML()
        yaml_writer.indent(mapping=2, sequence=4, offset=2)
        yaml_writer.preserve_quotes = True
        
        # Process the response to extract tasks and handlers more reliably
        response = converter.client.messages.create(
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            messages=[
                {"role": "user", "content": f"""Convert this Chef recipe to Ansible, clearly separating tasks and handlers:

```ruby
{chef_content}
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
```"""}
            ]
        )
        
        response_text = response.content[0].text
        print("\nLLM Response:\n")
        print(response_text)
        print("\n")
        
        # Extract tasks and handlers using regex
        import re
        
        # Look for sections labeled as tasks and handlers
        tasks_section = re.search(r'#\s*Tasks[^\n]*\n\s*```(?:yaml|yml)?\s*(.*?)```', response_text, re.DOTALL | re.IGNORECASE)
        handlers_section = re.search(r'#\s*Handlers[^\n]*\n\s*```(?:yaml|yml)?\s*(.*?)```', response_text, re.DOTALL | re.IGNORECASE)
        
        if tasks_section:
            tasks_content = tasks_section.group(1).strip()
        else:
            # Fallback to finding the first YAML block
            first_block = re.search(r'```(?:yaml|yml)\s*(.*?)```', response_text, re.DOTALL)
            tasks_content = first_block.group(1).strip() if first_block else ""
            
        if handlers_section:
            handlers_content = handlers_section.group(1).strip()
        else:
            # Fallback to finding the second YAML block
            yaml_blocks = re.findall(r'```(?:yaml|yml)\s*(.*?)```', response_text, re.DOTALL)
            handlers_content = yaml_blocks[1].strip() if len(yaml_blocks) > 1 else ""
        
        # Parse YAML content
        import yaml
        tasks = yaml.safe_load(tasks_content) or []
        handlers = yaml.safe_load(handlers_content) or []
        
        # Write to output file
        with open(output_file, 'w') as f:
            print(f"Writing tasks to {args.output_file}...")
            f.write("# Tasks (tasks/main.yml)\n")
            yaml_writer.dump(tasks, f)
            
            if handlers:
                f.write("\n# Handlers (handlers/main.yml)\n")
                yaml_writer.dump(handlers, f)
        
        print("Conversion completed successfully!")
        print(f"Output written to {args.output_file}")
        
    except Exception as e:
        print(f"Error during conversion: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
