# Chef to Ansible Converter

A Python-based tool that leverages Anthropic's Claude API to automatically convert Chef cookbooks to Ansible playbooks.

## Features

- Clone and process Chef repositories
- Parse Chef cookbook structures and recipes
- Convert Chef code to Ansible using Anthropic's Claude API
- Generate properly formatted Ansible playbooks and roles
- Validate generated Ansible code

## Security Notice

⚠️ **IMPORTANT**: Do not use this tool with repositories containing sensitive information, credentials, or proprietary code. All code submitted for conversion is processed through external API services and may be stored or logged. Use only with non-sensitive, public, or test repositories.

## Requirements

- Python 3.8+
- Git
- Anthropic API key

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python chef_to_ansible.py convert --repo-url <git-repo-url> --output-dir <output-directory>
```

## Architecture

The tool consists of several components:

1. **Repository Handler**: Manages Git operations to clone and process Chef repositories
2. **Chef Parser**: Extracts and understands Chef cookbook structures and recipes
3. **LLM Conversion Engine**: Core component that transforms Chef code to Ansible using Claude
4. **Ansible Generator**: Creates properly formatted Ansible playbooks and roles
5. **Validation Engine**: Ensures generated Ansible code is syntactically correct
