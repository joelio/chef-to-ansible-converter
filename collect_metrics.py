#!/usr/bin/env python3
"""
Metrics collection script for Chef to Ansible converter
Collects and stores metrics from conversion runs
"""

import os
import sys
import json
import time
import argparse
import datetime
from pathlib import Path
import yaml
import re

class MetricsCollector:
    """Collects metrics from Chef to Ansible conversion runs"""
    
    def __init__(self, metrics_dir="metrics"):
        """Initialize the metrics collector"""
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.metrics = {
            "timestamp": datetime.datetime.now().isoformat(),
            "runs": []
        }
    
    def analyze_ansible_role(self, role_dir):
        """
        Analyze an Ansible role for metrics
        
        Args:
            role_dir (Path): Path to the Ansible role directory
            
        Returns:
            dict: Metrics for the role
        """
        role_metrics = {
            "name": role_dir.name,
            "task_count": 0,
            "handler_count": 0,
            "variable_count": 0,
            "template_count": 0,
            "fqcn_compliance": 0,  # Percentage of tasks using FQCN
            "capitalization_compliance": 0,  # Percentage of tasks with capitalized names
            "boolean_compliance": 0,  # Percentage of tasks using true/false vs yes/no
            "variable_definition_compliance": 0,  # Percentage of used variables that are defined
        }
        
        # Analyze tasks
        tasks_file = role_dir / "tasks" / "main.yml"
        if tasks_file.exists():
            try:
                with open(tasks_file, "r") as f:
                    tasks_content = f.read()
                    tasks = yaml.safe_load(tasks_content)
                    if tasks is not None:
                        role_metrics["task_count"] = len(tasks)
                        
                        # Check FQCN compliance
                        fqcn_count = 0
                        capitalized_count = 0
                        boolean_count = 0
                        
                        for task in tasks:
                            # Check for FQCN
                            if any(k.startswith("ansible.") for k in task.keys() if k != "name"):
                                fqcn_count += 1
                            
                            # Check for capitalization in task names
                            if "name" in task and task["name"][0].isupper():
                                capitalized_count += 1
                            
                            # Check for true/false usage
                            task_str = str(task)
                            if "true" in task_str or "false" in task_str:
                                boolean_count += 1
                        
                        if role_metrics["task_count"] > 0:
                            role_metrics["fqcn_compliance"] = fqcn_count / role_metrics["task_count"] * 100
                            role_metrics["capitalization_compliance"] = capitalized_count / role_metrics["task_count"] * 100
                            role_metrics["boolean_compliance"] = boolean_count / role_metrics["task_count"] * 100
            except Exception as e:
                print(f"Error analyzing tasks: {str(e)}")
        
        # Analyze handlers
        handlers_file = role_dir / "handlers" / "main.yml"
        if handlers_file.exists():
            try:
                with open(handlers_file, "r") as f:
                    handlers_content = f.read()
                    handlers = yaml.safe_load(handlers_content)
                    if handlers is not None:
                        role_metrics["handler_count"] = len(handlers)
            except Exception as e:
                print(f"Error analyzing handlers: {str(e)}")
        
        # Analyze variables
        defaults_file = role_dir / "defaults" / "main.yml"
        if defaults_file.exists():
            try:
                with open(defaults_file, "r") as f:
                    defaults_content = f.read()
                    defaults = yaml.safe_load(defaults_content)
                    if defaults is not None:
                        role_metrics["variable_count"] = len(defaults)
                        
                        # Check variable definition compliance
                        if role_metrics["task_count"] > 0:
                            # Extract variable references from tasks
                            var_pattern = re.compile(r"{{\s*(\w+)(?:\.\w+)*\s*(?:\|\s*\w+(?:\(.*?\))?)*\s*}}")
                            task_vars = set()
                            
                            with open(tasks_file, "r") as f:
                                tasks_content = f.read()
                                matches = var_pattern.findall(tasks_content)
                                task_vars.update(matches)
                            
                            # Count how many referenced variables are defined
                            defined_vars = set(defaults.keys()) if defaults else set()
                            defined_var_count = len(task_vars.intersection(defined_vars))
                            
                            if len(task_vars) > 0:
                                role_metrics["variable_definition_compliance"] = defined_var_count / len(task_vars) * 100
            except Exception as e:
                print(f"Error analyzing variables: {str(e)}")
        
        # Count templates
        templates_dir = role_dir / "templates"
        if templates_dir.exists():
            role_metrics["template_count"] = len(list(templates_dir.glob("*.j2")))
        
        return role_metrics
    
    def collect_run_metrics(self, cookbook_name, output_dir, execution_time):
        """
        Collect metrics for a conversion run
        
        Args:
            cookbook_name (str): Name of the cookbook that was converted
            output_dir (Path): Directory containing the generated Ansible roles
            execution_time (float): Execution time in seconds
            
        Returns:
            dict: Metrics for the run
        """
        run_metrics = {
            "cookbook_name": cookbook_name,
            "execution_time": execution_time,
            "role_count": 0,
            "roles": []
        }
        
        # Find all roles in the output directory
        for role_dir in output_dir.iterdir():
            if role_dir.is_dir() and (role_dir / "tasks").exists():
                role_metrics = self.analyze_ansible_role(role_dir)
                run_metrics["roles"].append(role_metrics)
                run_metrics["role_count"] += 1
        
        self.metrics["runs"].append(run_metrics)
        return run_metrics
    
    def save_metrics(self, filename=None):
        """
        Save metrics to a JSON file
        
        Args:
            filename (str, optional): Filename to save metrics to.
                If not provided, a timestamped filename will be used.
                
        Returns:
            Path: Path to the saved metrics file
        """
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"metrics_{timestamp}.json"
        
        metrics_file = self.metrics_dir / filename
        
        with open(metrics_file, "w") as f:
            json.dump(self.metrics, f, indent=2)
        
        return metrics_file
    
    def generate_summary(self):
        """
        Generate a summary of the metrics
        
        Returns:
            str: Summary text
        """
        summary = []
        summary.append("# Chef to Ansible Conversion Metrics Summary")
        summary.append(f"Generated: {self.metrics['timestamp']}")
        summary.append("")
        
        total_roles = sum(run["role_count"] for run in self.metrics["runs"])
        total_tasks = sum(sum(role["task_count"] for role in run["roles"]) for run in self.metrics["runs"])
        total_handlers = sum(sum(role["handler_count"] for role in run["roles"]) for run in self.metrics["runs"])
        total_templates = sum(sum(role["template_count"] for role in run["roles"]) for run in self.metrics["runs"])
        
        summary.append(f"Total Cookbooks: {len(self.metrics['runs'])}")
        summary.append(f"Total Roles: {total_roles}")
        summary.append(f"Total Tasks: {total_tasks}")
        summary.append(f"Total Handlers: {total_handlers}")
        summary.append(f"Total Templates: {total_templates}")
        summary.append("")
        
        # Calculate compliance averages
        if total_roles > 0:
            avg_fqcn = sum(
                sum(role["fqcn_compliance"] * role["task_count"] for role in run["roles"]) 
                for run in self.metrics["runs"]
            ) / total_tasks if total_tasks > 0 else 0
            
            avg_cap = sum(
                sum(role["capitalization_compliance"] * role["task_count"] for role in run["roles"]) 
                for run in self.metrics["runs"]
            ) / total_tasks if total_tasks > 0 else 0
            
            avg_bool = sum(
                sum(role["boolean_compliance"] * role["task_count"] for role in run["roles"]) 
                for run in self.metrics["runs"]
            ) / total_tasks if total_tasks > 0 else 0
            
            avg_var_def = sum(
                sum(role["variable_definition_compliance"] * role["task_count"] for role in run["roles"]) 
                for run in self.metrics["runs"]
            ) / total_tasks if total_tasks > 0 else 0
            
            summary.append("## Compliance Metrics")
            summary.append(f"- FQCN Compliance: {avg_fqcn:.2f}%")
            summary.append(f"- Task Name Capitalization: {avg_cap:.2f}%")
            summary.append(f"- Boolean Values (true/false): {avg_bool:.2f}%")
            summary.append(f"- Variable Definition: {avg_var_def:.2f}%")
            summary.append("")
        
        # Per-run metrics
        summary.append("## Per-Cookbook Metrics")
        for run in self.metrics["runs"]:
            summary.append(f"### {run['cookbook_name']}")
            summary.append(f"- Execution Time: {run['execution_time']:.2f} seconds")
            summary.append(f"- Generated Roles: {run['role_count']}")
            
            for role in run["roles"]:
                summary.append(f"  - {role['name']}: {role['task_count']} tasks, {role['handler_count']} handlers, {role['variable_count']} variables")
                if role['task_count'] > 0:
                    summary.append(f"    - FQCN Compliance: {role['fqcn_compliance']:.2f}%")
                    summary.append(f"    - Task Name Capitalization: {role['capitalization_compliance']:.2f}%")
                    summary.append(f"    - Boolean Values (true/false): {role['boolean_compliance']:.2f}%")
                    summary.append(f"    - Variable Definition: {role['variable_definition_compliance']:.2f}%")
            
            summary.append("")
        
        return "\n".join(summary)
    
    def save_summary(self, filename=None):
        """
        Save summary to a Markdown file
        
        Args:
            filename (str, optional): Filename to save summary to.
                If not provided, a timestamped filename will be used.
                
        Returns:
            Path: Path to the saved summary file
        """
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"summary_{timestamp}.md"
        
        summary_file = self.metrics_dir / filename
        
        with open(summary_file, "w") as f:
            f.write(self.generate_summary())
        
        return summary_file
    
    def generate_historical_data(self):
        """
        Generate historical data from all metrics files
        
        Returns:
            dict: Historical metrics data
        """
        historical_data = {
            "timestamps": [],
            "fqcn_compliance": [],
            "capitalization_compliance": [],
            "boolean_compliance": [],
            "variable_definition_compliance": []
        }
        
        for metrics_file in sorted(self.metrics_dir.glob("metrics_*.json")):
            try:
                with open(metrics_file, "r") as f:
                    metrics = json.load(f)
                
                if "timestamp" in metrics and "runs" in metrics and metrics["runs"]:
                    historical_data["timestamps"].append(metrics["timestamp"])
                    
                    # Calculate averages for this metrics file
                    total_tasks = sum(sum(role["task_count"] for role in run["roles"]) for run in metrics["runs"])
                    
                    if total_tasks > 0:
                        avg_fqcn = sum(
                            sum(role.get("fqcn_compliance", 0) * role["task_count"] for role in run["roles"]) 
                            for run in metrics["runs"]
                        ) / total_tasks
                        
                        avg_cap = sum(
                            sum(role.get("capitalization_compliance", 0) * role["task_count"] for role in run["roles"]) 
                            for run in metrics["runs"]
                        ) / total_tasks
                        
                        avg_bool = sum(
                            sum(role.get("boolean_compliance", 0) * role["task_count"] for role in run["roles"]) 
                            for run in metrics["runs"]
                        ) / total_tasks
                        
                        avg_var_def = sum(
                            sum(role.get("variable_definition_compliance", 0) * role["task_count"] for role in run["roles"]) 
                            for run in metrics["runs"]
                        ) / total_tasks
                        
                        historical_data["fqcn_compliance"].append(avg_fqcn)
                        historical_data["capitalization_compliance"].append(avg_cap)
                        historical_data["boolean_compliance"].append(avg_bool)
                        historical_data["variable_definition_compliance"].append(avg_var_def)
            except Exception as e:
                print(f"Error processing metrics file {metrics_file}: {str(e)}")
        
        return historical_data

def main():
    parser = argparse.ArgumentParser(description='Collect metrics from Chef to Ansible conversion runs')
    parser.add_argument('--output-dir', type=str, default='ansible_roles', help='Directory containing the output Ansible roles')
    parser.add_argument('--cookbook-name', type=str, required=True, help='Name of the cookbook that was converted')
    parser.add_argument('--metrics-dir', type=str, default='metrics', help='Directory to store metrics data')
    parser.add_argument('--execution-time', type=float, help='Execution time in seconds')
    
    args = parser.parse_args()
    
    collector = MetricsCollector(metrics_dir=args.metrics_dir)
    
    if args.execution_time is None:
        # If execution time wasn't provided, use 0
        args.execution_time = 0
    
    collector.collect_run_metrics(
        args.cookbook_name,
        Path(args.output_dir),
        args.execution_time
    )
    
    metrics_file = collector.save_metrics()
    summary_file = collector.save_summary()
    
    print(f"Metrics saved to: {metrics_file}")
    print(f"Summary saved to: {summary_file}")

if __name__ == "__main__":
    main()
