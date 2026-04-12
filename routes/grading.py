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
            student=results_data['student_info'],
            results_path=results_path
        )
    except Exception as e:
        flash(f'Error loading results: {str(e)}', 'error')
        return redirect(url_for('upload.upload_page'))
    
@grading_bp.route('/grading/save', methods=['POST'])
def save_results():
    """
    Save the edited grading results (FR-29).
    The marker has reviewed and potentially edited scores and feedback.
    We save this as the final version.
    """
    results_path = request.form.get('results_path')
    
    if not results_path or not os.path.exists(results_path):
        flash('Could not find results to save.', 'error')
        return redirect(url_for('upload.upload_page'))
    
    # Load the original results
    with open(results_path, 'r') as f:
        results_data = json.load(f)
    
    # Update with edited values
    criteria_count = int(request.form.get('criteria_count', 0))
    
    total_weighted_score = 0
    total_weight = 0
    
    for i in range(criteria_count):
        new_score = float(request.form.get(f'score_{i}', 0))
        new_feedback = request.form.get(f'feedback_{i}', '')
        weighting = float(request.form.get(f'weighting_{i}', 0))
        
        # Update the criterion result
        results_data['grading_result']['criteria_results'][i]['score'] = new_score
        results_data['grading_result']['criteria_results'][i]['feedback'] = new_feedback
        
        # Recalculate grade band
        if new_score >= 80:
            band = '80-100'
        elif new_score >= 70:
            band = '70-79'
        elif new_score >= 60:
            band = '60-69'
        elif new_score >= 50:
            band = '50-59'
        elif new_score >= 40:
            band = '40-49'
        elif new_score >= 30:
            band = '30-39'
        else:
            band = '0-29'
        
        results_data['grading_result']['criteria_results'][i]['grade_band'] = band
        results_data['grading_result']['criteria_results'][i]['selected_band'] = band
        
        total_weighted_score += new_score * weighting
        total_weight += weighting
    
    # Update overall summary
    results_data['grading_result']['overall_summary'] = request.form.get('overall_summary', '')
    
    # Recalculate overall score (FR-28)
    if total_weight > 0:
        overall_score = round(total_weighted_score / total_weight, 1)
    else:
        overall_score = 0
    
    results_data['grading_result']['overall_score'] = overall_score
    
    # Mark as reviewed/edited by marker
    results_data['grading_result']['marker_reviewed'] = True
    
    # Save back to file
    with open(results_path, 'w') as f:
        json.dump(results_data, f, indent=2)
    
    flash('Results saved successfully! Scores and feedback have been updated.', 'success')
    
    # Reload the page with updated results
    session['results_path'] = results_path
    return redirect(url_for('grading.grading_page'))