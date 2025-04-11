"""Gunicorn configuration for Chef to Ansible Converter"""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = 2
timeout = 120  # Increased timeout for longer conversions
worker_class = "gevent"
threads = 4
accesslog = "-"
errorlog = "-"
loglevel = "info"
