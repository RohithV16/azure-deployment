import os
import sys
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g
import create_pr

# Add parent directory to path to import deployment_dev
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Import the deployment script as a module
import deployment_dev

from webapp.models import db, DeploymentLog

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Mock user for logging
class MockUser:
    username = "admin"
    is_authenticated = True

current_user = MockUser()

@app.before_request
def before_request():
    # Helper to mock current_user for templates if needed
    g.user = current_user

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Removed create_tables / login logic for simplified access
def create_tables():
    with app.app_context():
        db.create_all()

# Initialize database
create_tables()

@app.route('/login')
def login():
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    return redirect(url_for('dashboard'))

@app.route('/')
def dashboard():
    # Get local logs
    logs = DeploymentLog.query.order_by(DeploymentLog.timestamp.desc()).limit(10).all()
    
    # Get Azure DevOps builds
    azure_builds = []
    try:
        azure_builds = deployment_dev.get_recent_successful_builds(limit=10)
    except Exception as e:
        logger.error(f"Error fetching Azure builds: {e}")
        
    return render_template('dashboard.html', logs=logs, azure_builds=azure_builds, current_user=current_user)

@app.route('/check', methods=['POST'])
def check_deployment():
    """
    Checks if a deployment is needed by running the logic from deployment_dev.py
    """
    try:
        # Re-implementing the check logic using imported functions
        def_id = deployment_dev.BUILD_DEFINITION_ID
        branch = deployment_dev.BRANCH
        
        # 1. Get last successful build
        build_info = deployment_dev.get_last_build_info(def_id, include_in_progress=False)
        if not build_info:
            return jsonify({'status': 'error', 'message': 'Failed to get last build info'})
            
        baseline_commit = build_info['source_version']
        
        # 2. Check for commit on branch (basic check)
        # For simplicity in this web view, we'll straight up look for PRs after this commit
        # akin to the script logic
        
        # 3. Get PR merges
        pr_merges = deployment_dev.get_pr_merges_after_commit(baseline_commit, branch)
        
        if pr_merges is None:
             return jsonify({'status': 'error', 'message': 'Failed to get PR merges'})
             
        result = {
            'status': 'success',
            'build_info': build_info,
            'pr_merges': pr_merges,
            'count': len(pr_merges)
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error checking deployment: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/deploy', methods=['POST'])
def trigger_deployment():
    try:
        def_id = deployment_dev.BUILD_DEFINITION_ID
        branch = deployment_dev.BRANCH
        
        # Use existing logic to trigger
        new_build_info = deployment_dev.trigger_new_build(def_id, branch)
        
        if new_build_info:
            # Log it
            log = DeploymentLog(
                triggered_by=current_user.username,
                status='Triggered',
                build_id=str(new_build_info.get('build_id')),
                build_number=new_build_info.get('build_number'),
                details=f"Triggered manually via Web UI. Build ID: {new_build_info.get('build_id')}"
            )
            db.session.add(log)
            db.session.commit()
            
            flash(f"Deployment triggered successfully! Build #{new_build_info.get('build_number')}")
            return redirect(url_for('dashboard'))
        else:
            flash("Failed to trigger deployment")
            return redirect(url_for('dashboard'))
            
    except Exception as e:
        flash(f"Error triggering deployment: {e}")
        return redirect(url_for('dashboard'))

@app.route('/create-pr', methods=['POST'])
def create_pr_route():
    try:
        title = request.form.get('title')
        description = request.form.get('description')
        source_branch = request.form.get('source_branch')
        target_branch = request.form.get('target_branch', 'dev')
        
        # Validation
        if not title or not source_branch:
             flash("Missing required fields (Title, Source Branch)")
             return redirect(url_for('dashboard'))

        # Get Repo ID
        repo_id = deployment_dev.get_repository_id(create_pr.REPOSITORY_NAME)
        if not repo_id:
             flash("Failed to get Repository ID")
             return redirect(url_for('dashboard'))

        # Create PR
        # create_pr.create_pull_request expects: repo_id, source_branch, target_branch, title, description
        result = create_pr.create_pull_request(repo_id, source_branch, target_branch, title, description)
        
        if result:
             flash(f"PR Created Successfully! ID: {result.get('pullRequestId')}")
        else:
             flash("Failed to create PR (API Error). Check logs.")
             
        return redirect(url_for('dashboard'))

    except Exception as e:
        logger.error(f"Error creating PR: {e}")
        flash(f"Error creating PR: {e}")
        return redirect(url_for('dashboard'))

import subprocess

@app.route('/dev', methods=['POST'])
def deploy_dev():
    try:
        # Run deployment_dev.py in background
        subprocess.Popen(["python", "deployment_dev.py"])
        flash("started dev deployment script in background")
        return jsonify({'status': 'success', 'message': 'Started DEV deployment script in background'})
    except Exception as e:
        logger.error(f"Error starting DEV script: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/stage', methods=['POST'])
def deploy_stage():
    try:
        # Run deployment_stage.py in background
        subprocess.Popen(["python", "deployment_stage.py"])
        flash("started stage deployment script in background")
        return jsonify({'status': 'success', 'message': 'Started STAGE deployment script in background'})
    except Exception as e:
        logger.error(f"Error starting STAGE script: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=1234)
