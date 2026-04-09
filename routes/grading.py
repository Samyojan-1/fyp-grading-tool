"""
Grading Routes
--------------
Handles display of grading results.
"""

import os
import json
from flask import Blueprint, render_template, request, flash, redirect, url_for, session

grading_bp = Blueprint('grading', __name__)


@grading_bp.route('/grading')
def grading_page():
    """Show the grading results page."""
    results_path = session.get('results_path')
    
    if not results_path:
        flash('No grading results available. Please upload a report first.', 'error')
        return redirect(url_for('upload.upload_page'))
    
    try:
        if not os.path.exists(results_path):
            flash('Results file not found. Please grade a report again.', 'error')
            return redirect(url_for('upload.upload_page'))
        
        with open(results_path, 'r') as f:
            results_data = json.load(f)
        
        return render_template('results.html',
            results=results_data['grading_result'],
            student=results_data['student_info']
        )
    except Exception as e:
        flash(f'Error loading results: {str(e)}', 'error')
        return redirect(url_for('upload.upload_page'))