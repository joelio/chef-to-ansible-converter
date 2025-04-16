# Chef to Ansible Converter Makefile
# Provides easy commands for building, running, and testing the converter

# Default configuration
CHEF_REPO_PATH ?= ./chef-repo
OUTPUT_PATH ?= ./output
LOG_LEVEL ?= INFO
MODEL ?= claude-3-7-sonnet-20250219

# IMPORTANT: API keys are never stored in the Makefile
# They are always passed from environment variables or .env file at runtime

# Docker image name
IMAGE_NAME = chef-to-ansible-converter

# Help command
.PHONY: help
help:
	@echo "Chef to Ansible Converter Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  build              Build the Docker image"
	@echo "  convert            Convert Chef cookbooks to Ansible roles"
	@echo "  validate           Validate generated Ansible roles"
	@echo "  web                Start the web UI"
	@echo "  test               Run tests on the converter"
	@echo "  clean              Remove temporary files and directories"
	@echo "  help               Show this help message"
	@echo ""
	@echo "Configuration (can be set via environment variables):"
	@echo "  CHEF_REPO_PATH     Path to Chef repository (default: $(CHEF_REPO_PATH))"
	@echo "  OUTPUT_PATH        Path for output Ansible roles (default: $(OUTPUT_PATH))"
	@echo "  API_KEY            Anthropic API key"
	@echo "  MODEL              Anthropic model to use (default: $(MODEL))"
	@echo "  LOG_LEVEL          Log level: DEBUG, INFO, WARNING, ERROR (default: $(LOG_LEVEL))"
	@echo ""
	@echo "Examples:"
	@echo "  make build"
	@echo "  make convert CHEF_REPO_PATH=./my-chef-repo OUTPUT_PATH=./my-ansible"
	@echo "  make web"
	@echo ""

# Create required directories
$(CHEF_REPO_PATH) $(OUTPUT_PATH):
	mkdir -p $@

# Build the Docker image
.PHONY: build
build:
	@echo "Building Docker image..."
	docker build -t $(IMAGE_NAME):latest .
	@echo "Docker image built successfully!"

# Convert Chef cookbooks to Ansible roles
.PHONY: convert
convert: $(CHEF_REPO_PATH) $(OUTPUT_PATH)
	@echo "Converting Chef cookbooks to Ansible roles..."
	@echo "Chef repository path: $(CHEF_REPO_PATH)"
	@echo "Output path: $(OUTPUT_PATH)"
	@echo "Using model: $(MODEL)"
	@echo "Log level: $(LOG_LEVEL)"
	@if [ -z "$$ANTHROPIC_API_KEY" ]; then \
		echo "Error: ANTHROPIC_API_KEY environment variable is required"; \
		echo "Please set it with: export ANTHROPIC_API_KEY=your_api_key"; \
		exit 1; \
	fi
	@echo "Using API key from environment variable"
	docker run -it --rm \
		-v $(CHEF_REPO_PATH):/input \
		-v $(OUTPUT_PATH):/output \
		-e ANTHROPIC_API_KEY="$$ANTHROPIC_API_KEY" \
		-e ANTHROPIC_MODEL="$(MODEL)" \
		-e CHEF_TO_ANSIBLE_LOG_LEVEL="$(LOG_LEVEL)" \
		$(IMAGE_NAME):latest convert

# Validate generated Ansible roles
.PHONY: validate
validate: $(OUTPUT_PATH)
	@echo "Validating Ansible roles..."
	@echo "Output path: $(OUTPUT_PATH)"
	@echo "Using model: $(MODEL)"
	@echo "Log level: $(LOG_LEVEL)"
	@if [ -z "$$ANTHROPIC_API_KEY" ]; then \
		echo "Error: ANTHROPIC_API_KEY environment variable is required"; \
		echo "Please set it with: export ANTHROPIC_API_KEY=your_api_key"; \
		exit 1; \
	fi
	@echo "Using API key from environment variable"
	docker run -it --rm \
		-v $(OUTPUT_PATH):/output \
		-e ANTHROPIC_API_KEY="$$ANTHROPIC_API_KEY" \
		-e ANTHROPIC_MODEL="$(MODEL)" \
		-e CHEF_TO_ANSIBLE_LOG_LEVEL="$(LOG_LEVEL)" \
		$(IMAGE_NAME):latest validate

# Start the web UI
.PHONY: web
web:
	@echo "Starting web UI on port 5000..."
	@echo "Output path: $(OUTPUT_PATH)"
	@echo "Using model: $(MODEL)"
	@echo "Log level: $(LOG_LEVEL)"
	@if [ -z "$$ANTHROPIC_API_KEY" ]; then \
		echo "Error: ANTHROPIC_API_KEY environment variable is required"; \
		echo "Please set it with: export ANTHROPIC_API_KEY=your_api_key"; \
		exit 1; \
	fi
	@echo "Using API key from environment variable"
	docker run -it --rm \
		-p 5000:5000 \
		-v $(OUTPUT_PATH):/output \
		-e ANTHROPIC_API_KEY="$$ANTHROPIC_API_KEY" \
		-e ANTHROPIC_MODEL="$(MODEL)" \
		-e CHEF_TO_ANSIBLE_LOG_LEVEL="$(LOG_LEVEL)" \
		$(IMAGE_NAME):latest web

# Run tests
.PHONY: test
test: $(CHEF_REPO_PATH) $(OUTPUT_PATH)
	@echo "Running tests..."
	@echo "Chef repository path: $(CHEF_REPO_PATH)"
	@echo "Output path: $(OUTPUT_PATH)"
	@echo "Using model: $(MODEL)"
	@echo "Log level: $(LOG_LEVEL)"
	@if [ -z "$$ANTHROPIC_API_KEY" ]; then \
		echo "Error: ANTHROPIC_API_KEY environment variable is required"; \
		echo "Please set it with: export ANTHROPIC_API_KEY=your_api_key"; \
		exit 1; \
	fi
	@if [ ! -d "$(CHEF_REPO_PATH)/hello-world" ]; then \
		echo "Cloning test repository..."; \
		git clone https://github.com/karmi/chef-solo-hello-world.git $(CHEF_REPO_PATH)/hello-world; \
	fi
	@echo "Converting test repository..."
	@echo "Using API key from environment variable"
	docker run -it --rm \
		-v $(CHEF_REPO_PATH)/hello-world:/input \
		-v $(OUTPUT_PATH):/output \
		-e ANTHROPIC_API_KEY="$$ANTHROPIC_API_KEY" \
		-e ANTHROPIC_MODEL="$(MODEL)" \
		-e CHEF_TO_ANSIBLE_LOG_LEVEL="$(LOG_LEVEL)" \
		$(IMAGE_NAME):latest convert
	@echo "Test completed successfully!"

# Clean up
.PHONY: clean
clean:
	@echo "Cleaning up..."
	rm -rf $(OUTPUT_PATH)/*
	@echo "Cleanup complete!"

# Default target
.DEFAULT_GOAL := help
