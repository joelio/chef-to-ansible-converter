# Chef to Ansible Converter

A Python-based tool that leverages Anthropic's Claude API to automatically convert Chef cookbooks to Ansible playbooks and roles, following Ansible best practices.

## Features

- Clone and process Chef repositories
- Parse Chef cookbook structures and recipes
- Convert Chef code to Ansible using Anthropic's Claude API
- Generate properly formatted Ansible playbooks and roles
- Validate generated Ansible code with ansible-lint
- Convert ERB templates to Jinja2 templates
- Handle Chef-specific patterns and idioms
- Comprehensive logging system for better debugging
- Web UI for easy conversion (optional)
- Robust error handling and validation

## Security Notice

⚠️ **IMPORTANT**: Do not use this tool with repositories containing sensitive information, credentials, or proprietary code. All code submitted for conversion is processed through external API services and may be stored or logged. Use only with non-sensitive, public, or test repositories.

## Requirements

- Python 3.8+
- Git
- Anthropic API key (Claude API)
- Ansible (for validation, optional)
- ansible-lint (for validation, optional)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Command Line Interface

```bash
# Basic usage
python cli.py <chef-repo-path> --output <output-directory> --api-key <your-api-key>

# Using environment variable for API key
export ANTHROPIC_API_KEY=your-api-key
python cli.py <chef-repo-path> --output <output-directory>

# With validation
python cli.py <chef-repo-path> --output <output-directory> --validate

# With verbose logging
python cli.py <chef-repo-path> --output <output-directory> --log-level DEBUG
```

### Using Makefile

The project includes a Makefile that simplifies common operations, especially when using Docker:

```bash
# Show all available commands
make help

# Build the Docker image
make build

# Convert Chef cookbooks to Ansible roles
make convert CHEF_REPO_PATH=./my-chef-repo OUTPUT_PATH=./my-ansible

# Validate generated Ansible roles
make validate OUTPUT_PATH=./my-ansible

# Start the web UI
make web

# Run tests on a sample repository
make test

# Clean up temporary files and directories
make clean
```

Environment variables can be used to configure the conversion process:

```bash
# Set the Anthropic API key
export ANTHROPIC_API_KEY=your_api_key

# Set the model to use
export MODEL=claude-3-7-sonnet-20250219

# Set the log level
export LOG_LEVEL=DEBUG

# Run conversion with the configured environment
make convert CHEF_REPO_PATH=./my-chef-repo OUTPUT_PATH=./my-ansible
```

### Web UI

The converter also includes a web-based user interface for easier use:

```bash
# Start the web UI
make web
```

Then open your browser to http://localhost:5000

## Architecture

The tool consists of several components:

1. **Repository Handler** (`repo_handler.py`): Manages Git operations to clone and process Chef repositories
2. **Chef Parser** (`chef_parser.py`): Extracts and understands Chef cookbook structures and recipes
3. **LLM Conversion Engine** (`llm_converter.py`): Core component that transforms Chef code to Ansible using Claude
4. **Ansible Generator** (`ansible_generator.py`): Creates properly formatted Ansible playbooks and roles
5. **Validation Engine** (`validator.py`): Ensures generated Ansible code is syntactically correct
6. **Logger** (`logger.py`): Provides structured logging throughout the application
7. **Configuration** (`config.py`): Manages application settings and API credentials
8. **CLI Interface** (`cli.py`): Command-line interface for the converter
9. **Web UI** (`web/app.py`): Optional web interface for easier use

## Environment Variables

The following environment variables can be used to configure the tool:

- `ANTHROPIC_API_KEY`: Your Anthropic API key for Claude
- `CHEF_TO_ANSIBLE_LOG_LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `CHEF_TO_ANSIBLE_LOG_FILE`: Path to log file (if not set, logs to console only)

## Testing

To run the automated tests that validate the converter's functionality:

```bash
# Run tests on a sample repository
make test
```

This will clone a test Chef repository, convert it to Ansible, and validate the results.

### Advanced Testing

For more comprehensive testing across multiple repositories, you can use the metrics collection functionality:

```bash
# Run the metrics collection to test against multiple repositories
make metrics
```

This will test the converter against several real-world Chef repositories and generate metrics on conversion quality.

## Testing Results

We've conducted extensive testing of the Chef to Ansible converter using multiple test harnesses and repositories. Here's what we found:

### Successful Conversions

The converter successfully handles:

1. **Basic Chef Resources**: 
   - package → ansible.builtin.package
   - service → ansible.builtin.service
   - template → ansible.builtin.template
   - file → ansible.builtin.file
   - directory → ansible.builtin.file with state: directory

2. **ERB to Jinja2 Conversion**: 
   - Variable substitution: `<%= node['attr'] %>` → `{{ attr }}`
   - Conditionals: `<% if ... %>` → `{% if ... %}`
   - Loops: `<% each do |item| %>` → `{% for item in items %}`

3. **Chef Notifications**: 
   - notifies → notify
   - subscribes → handlers

4. **Chef Attributes**: 
   - Node attributes → Ansible variables
   - Default attributes → defaults/main.yml

### Real-World Testing

We tested the converter against these real-world Chef repositories:

1. **chef-solo-hello-world**: Simple web application (3 tasks, 2 handlers, 2 templates)
2. **iptables**: Network firewall configuration (73 tasks, 7 handlers, 4 templates)
3. **auditd**: Security auditing (17 tasks, 4 handlers, 7 templates)

### Challenges and Areas for Improvement

1. **Complex Ruby Logic**: 
   - Ruby blocks and complex conditionals need more sophisticated conversion
   - Nested logic structures sometimes lose their original intent

2. **Custom Resources**: 
   - Chef custom resources often require manual conversion to Ansible modules
   - Domain-specific resources need special handling

3. **Platform-Specific Code**: 
   - OS-specific configurations need better mapping to Ansible facts
   - Some platform detection logic doesn't translate cleanly

4. **Convergence Testing**: 
   - Some converted roles pass linting but fail during actual execution
   - Dependencies and prerequisites sometimes need manual adjustment

### Performance

The LLM-based conversion process takes approximately:
- 3-5 seconds for simple recipes
- 30-60 seconds for complex cookbooks with multiple recipes

The quality of conversion is generally high, with most basic Chef patterns correctly translated to idiomatic Ansible code.

## Docker Deployment

The Chef to Ansible Converter can be easily deployed using Docker, which provides a consistent and isolated environment for running the converter without worrying about dependencies.

### Using Make (Recommended)

The project includes a Makefile for easy operation:

```bash
# Show available commands
make help

# Build the Docker image
make build

# Convert a Chef repository to Ansible roles
make convert CHEF_REPO_PATH=/path/to/chef-repo OUTPUT_PATH=/path/to/output

# Start the web UI
make web

# Run tests with a sample Chef repository
make test

# Clean up output directory
make clean
```

You can configure the converter by setting environment variables:

```bash
# Set your API key (required)
export ANTHROPIC_API_KEY=your_api_key

# Set the model to use (optional)
export MODEL=claude-3-7-sonnet-20250219

# Set the log level (optional)
export LOG_LEVEL=DEBUG

# Run with custom configuration
make convert CHEF_REPO_PATH=./my-chef-repo OUTPUT_PATH=./my-output
```

> **Security Note**: The Makefile never stores API keys. It securely passes them from environment variables to the Docker container at runtime. Your API key is never baked into any files or images.

### Using Shell Script

Alternatively, you can use the provided shell script:

1. Build the Docker image:
```bash
./run-docker.sh build
```

2. Convert a Chef repository to Ansible roles:
```bash
./run-docker.sh --input=/path/to/chef-repo --output=/path/to/output convert
```

3. Start the web UI:
```bash
./run-docker.sh web
```

### Docker Compose

You can also use Docker Compose to run the converter:

```bash
# Set your API key
export ANTHROPIC_API_KEY=your_api_key

# Set paths for Chef repo and output
export CHEF_REPO_PATH=/path/to/chef-repo
export OUTPUT_PATH=/path/to/output

# Run the converter
docker-compose up converter

# Or run the web UI
docker-compose up web
```

### Manual Docker Commands

If you prefer to use Docker directly:

```bash
# Build the image
docker build -t chef-to-ansible-converter .

# Run the converter
docker run -it --rm \
  -v /path/to/chef-repo:/input \
  -v /path/to/output:/output \
  -e ANTHROPIC_API_KEY=your_api_key \
  chef-to-ansible-converter convert

# Run the web UI
docker run -it --rm \
  -p 5000:5000 \
  -e ANTHROPIC_API_KEY=your_api_key \
  chef-to-ansible-converter web
```

## Recent Improvements

### Code Quality
- Replaced print statements with structured logging
- Improved exception handling with specific error types
- Moved imports to the top of files for better readability
- Enhanced subprocess usage with proper validation
- Added type hints for better IDE support

### Usability
- Added comprehensive logging system
- Improved error messages and feedback
- Enhanced CLI with more options and better help text
- Better handling of API keys and environment variables
- Added Docker deployment for easier usage

### Reliability
- Added more robust error handling
- Improved validation of generated Ansible code
- Better handling of edge cases in Chef recipes
- Containerized environment for consistent execution

## Project Structure

The Chef to Ansible Converter project is organized as follows:

```
├── Dockerfile              # Main Docker configuration
├── Makefile               # Build and run commands
├── README.md              # Project documentation
├── chef-repo/             # Test Chef repositories
├── cli.py                 # Command-line interface
├── docker-compose.yml     # Docker Compose configuration
├── docker-entrypoint.sh   # Docker container entry point
├── requirements.txt       # Python dependencies
├── run-docker.sh          # Alternative Docker runner script
├── run_web_ui.py          # Web UI starter
├── src/                   # Core source code
│   ├── ansible_generator.py  # Generates Ansible roles
│   ├── chef_parser.py        # Parses Chef cookbooks
│   ├── config.py             # Configuration settings
│   ├── llm_converter.py      # LLM conversion logic
│   ├── logger.py             # Logging system
│   ├── validator.py          # Validates generated code
│   └── ...                   # Other modules
├── tests/                 # Test suite
└── web/                   # Web UI components
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
