#!/usr/bin/env python3
"""
Web UI for Chef to Ansible Converter
"""

import os
import sys
import tempfile
import shutil
import json
import uuid
import logging
import traceback
import queue
import threading
from time import sleep
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session, Response
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, SubmitField, SelectField, HiddenField
from wtforms.validators import DataRequired, URL, Optional
from werkzeug.utils import secure_filename

# Add the parent directory to the path so we can import the converter modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import Config
from src.repo_handler import GitRepoHandler
from src.chef_parser import ChefParser
from src.llm_converter import LLMConverter
from src.ansible_generator import AnsibleGenerator
from src.validator import AnsibleValidator

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-for-chef-to-ansible')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size
app.config['UPLOAD_FOLDER'] = os.path.join(tempfile.gettempdir(), 'chef_to_ansible_uploads')
app.config['CONVERSION_FOLDER'] = os.path.join(tempfile.gettempdir(), 'chef_to_ansible_conversions')
app.config['ANTHROPIC_API_KEY'] = os.environ.get('ANTHROPIC_API_KEY', '')

# Store progress updates in a dictionary keyed by conversion ID
progress_updates = {}

# Configure logging
logger = logging.getLogger(__name__)


# Ensure upload and conversion directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['CONVERSION_FOLDER'], exist_ok=True)

# Forms
class GitRepoForm(FlaskForm):
    """Form for converting a Git repository"""
    repo_url = StringField('Git Repository URL', validators=[DataRequired(), URL()])
    api_key = StringField('Anthropic API Key (optional)', validators=[Optional()])
    model = SelectField('Anthropic Model', choices=[
        ('claude-3-7-sonnet-20250219', 'Claude 3.7 Sonnet (Latest)'),
        ('claude-3-5-sonnet-20241022', 'Claude 3.5 Sonnet'),
        ('claude-3-opus-20240229', 'Claude 3 Opus'),
        ('claude-3-haiku-20240307', 'Claude 3 Haiku')
    ])
    submit = SubmitField('Convert Repository')

class ChefRecipeForm(FlaskForm):
    """Form for converting a Chef recipe"""
    recipe_content = TextAreaField('Chef Recipe Content', validators=[DataRequired()])
    api_key = StringField('Anthropic API Key (optional)', validators=[Optional()])
    model = SelectField('Anthropic Model', choices=[
        ('claude-3-7-sonnet-20250219', 'Claude 3.7 Sonnet (Latest)'),
        ('claude-3-5-sonnet-20241022', 'Claude 3.5 Sonnet'),
        ('claude-3-opus-20240229', 'Claude 3 Opus'),
        ('claude-3-haiku-20240307', 'Claude 3 Haiku')
    ])
    submit = SubmitField('Convert Recipe')

class ChefFileForm(FlaskForm):
    """Form for converting a Chef file"""
    chef_file = FileField('Chef Recipe File', validators=[
        FileRequired(),
        FileAllowed(['rb'], 'Ruby files only!')
    ])
    api_key = StringField('Anthropic API Key (optional)', validators=[Optional()])
    model = SelectField('Anthropic Model', choices=[
        ('claude-3-7-sonnet-20250219', 'Claude 3.7 Sonnet (Latest)'),
        ('claude-3-5-sonnet-20241022', 'Claude 3.5 Sonnet'),
        ('claude-3-opus-20240229', 'Claude 3 Opus'),
        ('claude-3-haiku-20240307', 'Claude 3 Haiku')
    ])
    submit = SubmitField('Convert File')

# Routes
@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/progress/<conversion_id>')
def progress_stream(conversion_id):
    """Stream progress updates for a conversion"""
    def generate():
        # Initialize progress for this conversion if it doesn't exist
        if conversion_id not in progress_updates:
            progress_updates[conversion_id] = queue.Queue()
            # Send initial message
            logger.debug(f"Initializing progress stream for conversion ID: {conversion_id}")
            yield f"data: {json.dumps({'status': 'initializing', 'message': 'Initializing conversion...', 'progress': 0})}\n\n"
        
        q = progress_updates[conversion_id]
        
        # Keep the connection open until we receive a completion or error message
        completion_received = False
        while not completion_received:
            try:
                # Try to get an update from the queue with a timeout
                update = q.get(timeout=1)
                logger.debug(f"Sending update for {conversion_id}: {update}")
                yield f"data: {json.dumps(update)}\n\n"
                
                # If this is a completion or error message, set the flag to break the loop
                if update.get('status') in ['completed', 'error']:
                    logger.info(f"Received completion/error status for {conversion_id}, closing stream")
                    completion_received = True
                    # Send one more message to ensure the client receives the completion status
                    yield f"data: {json.dumps({'status': 'stream_end', 'message': 'Stream closed by server'})}\n\n"
            except queue.Empty:
                # Send a keep-alive message every second if there's no update
                yield f"data: {json.dumps({'status': 'waiting', 'message': 'Waiting for updates...'})}\n\n"
    
    # Set response headers to prevent caching
    headers = {
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',  # Disable buffering for Nginx
        'Connection': 'keep-alive'
    }
    
    return Response(generate(), mimetype='text/event-stream', headers=headers)

@app.route('/convert/repo', methods=['GET', 'POST'])
def convert_repo():
    """Convert a Git repository"""
    form = GitRepoForm()
    
    if form.validate_on_submit():
        # Get form data
        repo_url = form.repo_url.data
        api_key = form.api_key.data or app.config['ANTHROPIC_API_KEY']
        model = form.model.data
        
        # Generate a unique ID for this conversion
        conversion_id = str(uuid.uuid4())
        
        # Create a queue for progress updates
        progress_updates[conversion_id] = queue.Queue()
        
        # Create output directory
        output_dir = os.path.join(app.config['CONVERSION_FOLDER'], conversion_id)
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate the URLs before starting the thread (to avoid application context issues)
        # Make sure to use the correct route path
        results_url = f"/results/repo/{conversion_id}"
        download_url = f"/download/{conversion_id}"
        
        # Define progress callback function
        def progress_callback(update):
            if conversion_id in progress_updates:
                progress_updates[conversion_id].put(update)
        
        # Start conversion in a background thread
        def run_conversion():
            try:
                logger.info(f"Starting conversion of repository: {repo_url}")
                progress_callback({
                    'status': 'processing',
                    'message': f"Starting conversion of repository: {repo_url}",
                    'progress': 0
                })
                
                # Initialize the converter
                config = Config(api_key=api_key, model=model, verbose=True)
                repo_handler = GitRepoHandler()
                chef_parser = ChefParser()
                llm_converter = LLMConverter(config, progress_callback=progress_callback)
                ansible_generator = AnsibleGenerator()
                validator = AnsibleValidator()
                
                logger.debug("Initialized all converter components")
                progress_callback({
                    'status': 'processing',
                    'message': "Initialized converter components",
                    'progress': 5
                })
            
                # Clone the repository
                logger.info(f"Cloning repository: {repo_url}")
                progress_callback({
                    'status': 'processing',
                    'message': f"Cloning repository: {repo_url}",
                    'progress': 10
                })
                repo_path = repo_handler.clone_repository(repo_url)
                logger.debug(f"Repository cloned to: {repo_path}")
                
                # Find all cookbooks in the repository
                logger.info("Finding cookbooks in repository")
                progress_callback({
                    'status': 'processing',
                    'message': "Finding cookbooks in repository",
                    'progress': 20
                })
                cookbooks = chef_parser.find_cookbooks(repo_path)
                logger.info(f"Found {len(cookbooks)} cookbooks: {[c['name'] for c in cookbooks]}")
                progress_callback({
                    'status': 'processing',
                    'message': f"Found {len(cookbooks)} cookbooks",
                    'progress': 30
                })
            
                if not cookbooks:
                    progress_callback({
                        'status': 'error',
                        'message': 'No cookbooks found in the repository.',
                        'progress': 0
                    })
                    flash('No cookbooks found in the repository.', 'warning')
                    return redirect(url_for('index'))
                
                # Initialize results
                results = {
                    'conversion_id': conversion_id,
                    'repo_url': repo_url,
                    'success_count': 0,
                    'failed_count': 0,
                    'details': []
                }
            
                # Process each cookbook
                total_cookbooks = len(cookbooks)
                for i, cookbook in enumerate(cookbooks):
                    try:
                        logger.info(f"Processing cookbook: {cookbook['name']}")
                        progress_callback({
                            'status': 'processing',
                            'message': f"Processing cookbook {i+1}/{total_cookbooks}: {cookbook['name']}",
                            'progress': 30 + (i / total_cookbooks) * 40
                        })
                        
                        # Parse the cookbook
                        logger.debug(f"Parsing cookbook: {cookbook['path']}")
                        progress_callback({
                            'status': 'processing',
                            'message': f"Parsing cookbook: {cookbook['name']}",
                            'progress': 30 + (i / total_cookbooks) * 40 + 5
                        })
                        parsed_cookbook = chef_parser.parse_cookbook(cookbook['path'])
                        
                        if not parsed_cookbook['recipes']:
                            logger.warning(f"No recipes found in cookbook: {cookbook['name']}, skipping")
                            progress_callback({
                                'status': 'processing',
                                'message': f"No recipes found in cookbook: {cookbook['name']}, skipping",
                                'progress': 30 + (i / total_cookbooks) * 40 + 10
                            })
                            continue
                        
                        logger.info(f"Found {len(parsed_cookbook['recipes'])} recipes in cookbook {cookbook['name']}")
                        progress_callback({
                            'status': 'processing',
                            'message': f"Found {len(parsed_cookbook['recipes'])} recipes in cookbook {cookbook['name']}",
                            'progress': 30 + (i / total_cookbooks) * 40 + 15
                        })
                        
                        for recipe in parsed_cookbook['recipes']:
                            logger.debug(f"Recipe found: {recipe['name']}")
                        
                        # Convert the cookbook to Ansible
                        logger.info(f"Converting cookbook to Ansible: {cookbook['name']}")
                        progress_callback({
                            'status': 'processing',
                            'message': f"Converting cookbook {cookbook['name']}...",
                            'progress': 50 + (i / total_cookbooks) * 20
                        })
                        ansible_code = llm_converter.convert_cookbook(parsed_cookbook)
                        
                        # Make sure ansible_code has all required fields
                        if not isinstance(ansible_code, dict):
                            raise ValueError(f"Invalid conversion result for {cookbook['name']}: not a dictionary")
                            
                        # Add cookbook name to ansible_code if not present
                        if 'name' not in ansible_code:
                            ansible_code['name'] = cookbook['name']
                        
                        # Generate Ansible role
                        logger.info(f"Generating Ansible role: {cookbook['name']}")
                        ansible_path = os.path.join(output_dir, cookbook['name'])
                        os.makedirs(ansible_path, exist_ok=True)
                        progress_callback({
                            'status': 'processing',
                            'message': f"Generating Ansible role for {cookbook['name']}",
                            'progress': 70 + (i / total_cookbooks) * 20
                        })
                        ansible_generator.generate_ansible_role(ansible_code, ansible_path)
                        
                        # Validate the generated Ansible code
                        logger.info(f"Validating Ansible role: {cookbook['name']}")
                        progress_callback({
                            'status': 'processing',
                            'message': f"Validating Ansible role for {cookbook['name']}",
                            'progress': 70 + (i / total_cookbooks) * 20 + 5
                        })
                        validation_result = validator.validate(ansible_path)
                        logger.debug(f"Validation result: {validation_result}")
                    
                        results['details'].append({
                            'cookbook': cookbook['name'],
                            'success': validation_result['valid'],
                            'messages': validation_result['messages']
                        })
                        
                        if validation_result['valid']:
                            results['success_count'] += 1
                        else:
                            results['failed_count'] += 1
                            
                    except Exception as e:
                        logger.error(f"Error converting cookbook {cookbook['name']}: {str(e)}")
                        logger.error(traceback.format_exc())
                        
                        results['details'].append({
                            'cookbook': cookbook['name'],
                            'success': False,
                            'messages': [str(e)]
                        })
                        results['failed_count'] += 1
            
                # Clean up temporary files
                repo_handler.cleanup(repo_path)
                
                # Save results to a JSON file
                results_file = os.path.join(output_dir, 'results.json')
                logger.info(f"Saving results to: {results_file}")
                with open(results_file, 'w') as f:
                    json.dump(results, f, indent=2)
                
                # Make sure the file was created
                if os.path.exists(results_file):
                    logger.info(f"Results file created successfully: {results_file}")
                else:
                    logger.error(f"Failed to create results file: {results_file}")
                
                # Instead of using session, store results in a JSON file that can be read by the results page
                # We already saved the results to results.json above
                
                # Send final completion message
                completion_message = {
                    'status': 'completed',
                    'message': f"Conversion complete. Successfully converted {results['success_count']} cookbook(s). Failed to convert {results['failed_count']} cookbook(s).",
                    'progress': 100,
                    'redirect_url': results_url,
                    'download_url': download_url
                }
                
                # Log the completion message
                logger.info(f"Sending completion message: {completion_message}")
                
                # Send the completion message
                progress_callback(completion_message)
                
                # Sleep briefly to ensure the message is sent before the thread ends
                sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error during conversion: {str(e)}")
                logger.error(traceback.format_exc())
                progress_callback({
                    'status': 'error',
                    'message': f"Error during conversion: {str(e)}",
                    'progress': 100
                })
        
        # Start the conversion thread
        conversion_thread = threading.Thread(target=run_conversion)
        conversion_thread.daemon = True
        conversion_thread.start()
        
        # Redirect to a page that will show progress
        return redirect(url_for('show_progress', conversion_id=conversion_id))
    
    return render_template('convert_repo.html', form=form)

@app.route('/progress_page/<conversion_id>')
def show_progress(conversion_id):
    """Show progress page for a conversion"""
    return render_template('progress.html', conversion_id=conversion_id)

@app.route('/convert/recipe', methods=['GET', 'POST'])
def convert_recipe():
    """Convert a Chef recipe"""
    form = ChefRecipeForm()
    
    if form.validate_on_submit():
        recipe_content = form.recipe_content.data
        api_key = form.api_key.data or app.config['ANTHROPIC_API_KEY']
        model = form.model.data
        
        if not api_key:
            flash('Anthropic API key is required. Please provide it in the form or set the ANTHROPIC_API_KEY environment variable.', 'danger')
            return render_template('convert_recipe.html', form=form)
        
        try:
            # Initialize the converter
            config = Config(api_key=api_key, model=model, verbose=True)
            llm_converter = LLMConverter(config)
            
            # Create a mock recipe
            recipe = {
                'name': 'recipe',
                'content': recipe_content,
                'resources': []
            }
            
            # Convert the recipe
            result = llm_converter.convert_recipe(recipe)
            
            # Save the result to session
            session['recipe_result'] = {
                'tasks': result['tasks'],
                'handlers': result['handlers']
            }
            
            return redirect(url_for('recipe_results'))
        
        except Exception as e:
            flash(f'Error during conversion: {str(e)}', 'danger')
            return render_template('convert_recipe.html', form=form)
    
    return render_template('convert_recipe.html', form=form)

@app.route('/convert/file', methods=['GET', 'POST'])
def convert_file():
    """Convert a Chef file"""
    form = ChefFileForm()
    
    if form.validate_on_submit():
        api_key = form.api_key.data or app.config['ANTHROPIC_API_KEY']
        model = form.model.data
        
        if not api_key:
            flash('Anthropic API key is required. Please provide it in the form or set the ANTHROPIC_API_KEY environment variable.', 'danger')
            return render_template('convert_file.html', form=form)
        
        # Save the uploaded file
        chef_file = form.chef_file.data
        filename = secure_filename(chef_file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        chef_file.save(file_path)
        
        try:
            # Read the file content
            with open(file_path, 'r') as f:
                recipe_content = f.read()
            
            # Initialize the converter
            config = Config(api_key=api_key, model=model, verbose=True)
            llm_converter = LLMConverter(config)
            
            # Create a mock recipe
            recipe = {
                'name': filename.replace('.rb', ''),
                'content': recipe_content,
                'resources': []
            }
            
            # Convert the recipe
            result = llm_converter.convert_recipe(recipe)
            
            # Save the result to session
            session['recipe_result'] = {
                'tasks': result['tasks'],
                'handlers': result['handlers']
            }
            
            # Clean up
            os.remove(file_path)
            
            return redirect(url_for('recipe_results'))
        
        except Exception as e:
            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)
            
            flash(f'Error during conversion: {str(e)}', 'danger')
            return render_template('convert_file.html', form=form)
    
    return render_template('convert_file.html', form=form)

@app.route('/results/recipe')
def recipe_results():
    """Show the results of a recipe conversion"""
    recipe_result = session.get('recipe_result')
    
    if not recipe_result:
        flash('No recipe conversion results found.', 'warning')
        return redirect(url_for('index'))
    
    # Convert the result to YAML
    import yaml
    
    tasks_yaml = yaml.dump(recipe_result['tasks'], default_flow_style=False)
    handlers_yaml = yaml.dump(recipe_result['handlers'], default_flow_style=False) if recipe_result['handlers'] else None
    
    return render_template('recipe_results.html', tasks_yaml=tasks_yaml, handlers_yaml=handlers_yaml)

@app.route('/results/repo/<conversion_id>')
def conversion_results(conversion_id):
    """Show the results of a repository conversion"""
    conversion_dir = os.path.join(app.config['CONVERSION_FOLDER'], conversion_id)
    logger.info(f"Looking for conversion results in: {conversion_dir}")
    
    # List all files in the conversion directory for debugging
    if os.path.exists(conversion_dir):
        logger.info(f"Contents of conversion directory: {os.listdir(conversion_dir)}")
    else:
        logger.error(f"Conversion directory not found: {conversion_dir}")
        flash('Conversion directory not found.', 'warning')
        return redirect(url_for('index'))
    
    # Read results from the JSON file
    results_file = os.path.join(conversion_dir, 'results.json')
    logger.info(f"Looking for results file: {results_file}")
    
    if not os.path.exists(results_file):
        logger.error(f"Results file not found: {results_file}")
        
        # Try to create a default results file if it doesn't exist
        try:
            default_results = {
                'success_count': 0,
                'failed_count': 0,
                'details': []
            }
            with open(results_file, 'w') as f:
                json.dump(default_results, f, indent=2)
            logger.info(f"Created default results file: {results_file}")
        except Exception as e:
            logger.error(f"Failed to create default results file: {e}")
            flash('Conversion results not found.', 'warning')
            return redirect(url_for('index'))
        
    with open(results_file, 'r') as f:
        conversion_results = json.load(f)
    
    # Get the list of converted cookbooks
    cookbooks = []
    for item in os.listdir(conversion_dir):
        item_path = os.path.join(conversion_dir, item)
        if os.path.isdir(item_path) and item != '__pycache__':
            cookbooks.append(item)
    
    return render_template('conversion_results.html', 
                          results=conversion_results, 
                          conversion_id=conversion_id,
                          cookbooks=cookbooks)

@app.route('/download/<conversion_id>')
def download_conversion(conversion_id):
    """Download the converted Ansible roles as a zip file"""
    conversion_dir = os.path.join(app.config['CONVERSION_FOLDER'], conversion_id)
    
    if not os.path.exists(conversion_dir):
        flash('Conversion directory not found.', 'warning')
        return redirect(url_for('index'))
    
    # Create a zip file of the conversion directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_filename = f'ansible_roles_{timestamp}.zip'
    zip_path = os.path.join(app.config['CONVERSION_FOLDER'], f'{conversion_id}.zip')
    
    # Remove any existing zip file
    if os.path.exists(zip_path):
        os.remove(zip_path)
    
    # Create a new zip file with all the converted roles
    shutil.make_archive(zip_path[:-4], 'zip', conversion_dir)
    
    return send_file(zip_path, as_attachment=True, download_name=zip_filename)

@app.route('/view/<conversion_id>/<cookbook>/<file_type>')
def view_file(conversion_id, cookbook, file_type):
    """View a specific file from the conversion"""
    conversion_dir = os.path.join(app.config['CONVERSION_FOLDER'], conversion_id)
    
    if not os.path.exists(conversion_dir):
        flash('Conversion directory not found.', 'warning')
        return redirect(url_for('index'))
    
    cookbook_dir = os.path.join(conversion_dir, cookbook)
    
    if not os.path.exists(cookbook_dir):
        flash('Cookbook directory not found.', 'warning')
        return redirect(url_for('conversion_results', conversion_id=conversion_id))
    
    file_path = None
    if file_type == 'tasks':
        file_path = os.path.join(cookbook_dir, 'tasks', 'main.yml')
    elif file_type == 'handlers':
        file_path = os.path.join(cookbook_dir, 'handlers', 'main.yml')
    elif file_type == 'defaults':
        file_path = os.path.join(cookbook_dir, 'defaults', 'main.yml')
    elif file_type == 'meta':
        file_path = os.path.join(cookbook_dir, 'meta', 'main.yml')
    elif file_type == 'readme':
        file_path = os.path.join(cookbook_dir, 'README.md')
    
    if not file_path or not os.path.exists(file_path):
        flash(f'File {file_type} not found.', 'warning')
        return redirect(url_for('conversion_results', conversion_id=conversion_id))
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    return render_template('view_file.html', 
                          content=content, 
                          cookbook=cookbook, 
                          file_type=file_type,
                          conversion_id=conversion_id)

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
