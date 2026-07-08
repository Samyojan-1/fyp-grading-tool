"""
Grading Routes
--------------
Handles display of grading results.
"""
from services.export import export_results
import os
import json
from flask import Blueprint, render_template, request, flash, redirect, url_for, session

grading_bp = Blueprint('grading', __name__)

def get_batch_context():
    """
    Check if the results page is being viewed as part of a batch
    (URL like /grading?batch=batch_20260708_143210&report=3).

    Returns (results_path, batch_nav) where batch_nav holds the
    Previous/Next links, or (None, None) when not viewing a batch.
    """
    from services import batch_grader

    batch_id = request.args.get('batch')
    report_arg = request.args.get('report')

    if not batch_id or report_arg is None:
        return None, None

    status = batch_grader.load_status(batch_id)
    if status is None:
        return None, None

    try:
        report_index = int(report_arg)
        entry = status['reports'][report_index]
    except (ValueError, IndexError):
        return None, None

    results_path = os.path.join(entry['folder'], 'grading_results.json')

    # Previous/Next only steps through reports that actually got graded
    graded = [r['index'] for r in status['reports'] if r['status'] == 'done']
    prev_url = None
    next_url = None
    position = None
    if report_index in graded:
        pos = graded.index(report_index)
        position = pos + 1
        if pos > 0:
            prev_url = url_for('grading.grading_page', batch=batch_id, report=graded[pos - 1])
        if pos < len(graded) - 1:
            next_url = url_for('grading.grading_page', batch=batch_id, report=graded[pos + 1])

    batch_nav = {
        'batch_id': batch_id,
        'report_index': report_index,
        'position': position,
        'total': len(graded),
        'prev_url': prev_url,
        'next_url': next_url,
        'batch_url': url_for('batch.batch_page', batch_id=batch_id),
    }
    return results_path, batch_nav


@grading_bp.route('/grading')
def grading_page(): # Shows the grading results page

    # Batch mode: the URL tells us which report to show
    results_path, batch_nav = get_batch_context()

    # Single mode: fall back to the path stored in the session
    if not results_path:
        results_path = session.get('results_path')

    # to check if we have a path
    if not results_path:
        flash('No grading results available. Please upload a report first.', 'error')
        return redirect(url_for('upload.upload_page'))

    try: # to check if that path leads to an actual file
        if not os.path.exists(results_path):
            flash('Results file not found. Please grade a report again.', 'error')
            return redirect(url_for('upload.upload_page'))

        with open(results_path, 'r') as f:
            results_data = json.load(f)

        # Remember this path so save/export keep working in batch mode too
        session['results_path'] = results_path

        #loading results.html with these variables
        return render_template('results.html',
            results=results_data['grading_result'],
            student=results_data['student_info'],
            results_path=results_path,
            batch_nav=batch_nav
        )
    except Exception as e:
        flash(f'Error loading results: {str(e)}', 'error')
        return redirect(url_for('upload.upload_page'))
    
@grading_bp.route('/grading/save', methods=['POST'])
def save_results(): # Save the edited grading results

    results_path = request.form.get('results_path') #getting the path to grading_results.json file 
    
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
    
    # Recalculate overall score
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

    # If we came from a batch, go back to the same report in the batch
    batch_id = request.form.get('batch')
    report_index = request.form.get('report')
    if batch_id:
        return redirect(url_for('grading.grading_page', batch=batch_id, report=report_index))

    return redirect(url_for('grading.grading_page'))

@grading_bp.route('/grading/export')
def export_grading():
    # Export grading results as PDF and Excel 
    results_path = session.get('results_path')
    
    if not results_path or not os.path.exists(results_path):
        flash('No results to export. Please grade a report first.', 'error')
        return redirect(url_for('upload.upload_page'))
    
    with open(results_path, 'r') as f:
        results_data = json.load(f)
    
    # Get the submission folder from the results path
    submission_folder = os.path.dirname(results_path)
    
    # Export both formats
    export_result = export_results(results_data, submission_folder)
    
    # Check for errors
    messages = []
    if 'error' in export_result.get('excel', {}):
        messages.append(f'Excel export failed: {export_result["excel"]["error"]}')
    else:
        messages.append(f'Excel exported successfully')
    
    if 'error' in export_result.get('pdf', {}):
        messages.append(f'PDF export failed: {export_result["pdf"]["error"]}')
    else:
        messages.append(f'PDF exported successfully')
    
    flash(f'Export complete: {". ".join(messages)}. Files saved to submission folder.', 'success')

    # If we came from a batch, go back to the same report in the batch
    batch_id = request.args.get('batch')
    report_index = request.args.get('report')
    if batch_id:
        return redirect(url_for('grading.grading_page', batch=batch_id, report=report_index))

    return redirect(url_for('grading.grading_page'))