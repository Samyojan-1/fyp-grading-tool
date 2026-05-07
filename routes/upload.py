import os
import re
import json
import base64
from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from werkzeug.utils import secure_filename
import config
from services.file_parser import extract_text
from services.rubric_parser import parse_rubric, save_rubric, load_rubric
from services.ai_grader import grade_report

upload_bp = Blueprint('upload', __name__)

#Getting the list of previously saved rubric JSON files from the rubrics folder
def get_saved_rubrics():
    rubric_folder = config.RUBRIC_FOLDER
    if not os.path.exists(rubric_folder):
        os.makedirs(rubric_folder)
        return []
    return [f for f in os.listdir(rubric_folder) if f.endswith('.json')] #Listing .json files

 # Checking if the filename has an allowed extension
def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


@upload_bp.route('/')
def upload_page(): # Loading the upload page
    saved_rubrics = get_saved_rubrics()
    return render_template('upload.html', saved_rubrics=saved_rubrics)


@upload_bp.route('/upload', methods=['POST'])
def handle_upload():
    """
    Handles form submission.
    This runs when the user clicks 'Start Grading'.
    
    request.files: contains uploaded files
    request.form: contains text fields (e.g. student_name)
    """
    
    # -- Get student details --
    student_name = request.form.get('student_name', '').strip()
    student_number = request.form.get('student_number', '').strip().upper()
    
    if not student_name:
        flash('Please enter a student name.', 'error')
        return redirect(url_for('upload.upload_page'))
    
    if not student_number:
        flash('Please enter a student number.', 'error')
        return redirect(url_for('upload.upload_page'))
    
    # Server-side validation of student number format
    # re.match() checks if the string matches the pattern from the start
    # ^ = start, $ = end, \d = any digit, {7} = exactly 7 times
    if not re.match(r'^UP\d{7}$', student_number):
        flash('Invalid student number. Must be UP followed by 7 digits (e.g. UP2303086).', 'error')
        return redirect(url_for('upload.upload_page'))
    
    # -- Validate the report file --
    if 'report' not in request.files:
        flash('No report file uploaded.', 'error')
        return redirect(url_for('upload.upload_page'))
    
    report_file = request.files['report'] # gets the file from the form input
    
    # This can happen if user submits form without selecting a file
    if report_file.filename == '':
        flash('No report file selected.', 'error')
        return redirect(url_for('upload.upload_page'))
    
    if not allowed_file(report_file.filename, config.ALLOWED_REPORT_EXTENSIONS):
        flash('Invalid report format. Please upload a PDF or DOCX file.', 'error')
        return redirect(url_for('upload.upload_page'))
    
    # -- Handle rubric --
    rubric_choice = request.form.get('rubric_choice')
    rubric_filename = None
    
    if rubric_choice == 'upload_new':
        # They're uploading a new rubric
        if 'rubric' not in request.files or request.files['rubric'].filename == '':
            flash('Please upload a rubric file or select a saved one.', 'error')
            return redirect(url_for('upload.upload_page'))
        
        rubric_file = request.files['rubric']
        
        if not allowed_file(rubric_file.filename, config.ALLOWED_RUBRIC_EXTENSIONS):
            flash('Invalid rubric format. Please upload a PDF file.', 'error')
            return redirect(url_for('upload.upload_page'))
    else:
        # They selected a previously saved rubric
        rubric_filename = rubric_choice
    
    # -- Create submission folder --
    # Format: UP2303086_SamDev_2026-04-02
    date_str = datetime.now().strftime('%Y-%m-%d')
    folder_name = f"{student_number}_{secure_filename(student_name)}_{date_str}"
    submission_folder = os.path.join(config.UPLOAD_FOLDER, folder_name)
    os.makedirs(submission_folder, exist_ok=True)
    
    # -- Save the report --
    report_filename = secure_filename(report_file.filename)
    report_path = os.path.join(submission_folder, report_filename)
    report_file.save(report_path)
    
    # --- Save the rubric (if new upload) ---
    if rubric_choice == 'upload_new':
        rubric_filename = secure_filename(rubric_file.filename)
        rubric_path = os.path.join(submission_folder, rubric_filename)
        rubric_file.save(rubric_path)
    
    # --- Extract text from the report ---
    result = extract_text(report_path)
    
    if 'error' in result:
        flash(f'Warning: Could not extract text from report — {result["error"]}', 'error')
        return redirect(url_for('upload.upload_page'))
    
    if result.get('is_scanned'):
        flash('Warning: This PDF appears to be scanned (no extractable text). '
              'It has been flagged for manual review.', 'error')
        return redirect(url_for('upload.upload_page'))
    
    # --- Handle rubric ---
    if rubric_choice == 'upload_new':
        # Parse the new rubric with AI
        flash('Parsing rubric... This may take a moment.', 'success')
        parsed = parse_rubric(rubric_path)
        
        if 'error' in parsed:
            flash(f'Rubric parsing failed: {parsed["error"]}', 'error')
            return redirect(url_for('upload.upload_page'))
        
        # Show verification page 
        # return render_template('rubric_verify.html',
        #     parsed_rubric=parsed,
        #     rubric_json=json.dumps(parsed),  # Pass as JSON string for the hidden form field
        #     rubric_filename=rubric_filename,
        #     submission_folder=submission_folder
        # )

        # import base64
        # Encoding the JSON as base64 to avoid quote/special character issues in HTML
        rubric_json_b64 = base64.b64encode(json.dumps(parsed).encode()).decode()
        
        # Saving report text so we can grade after rubric confirmation
        report_text_for_later = result['text']
        context_path = os.path.join(submission_folder, 'grading_context.tmp')
        with open(context_path, 'w') as f:
            json.dump({
                'report_text': report_text_for_later,
                'student_info': {
                    'name': student_name,
                    'number': student_number,
                    'report_filename': report_filename,
                    'submission_folder': submission_folder
                }
            }, f)

        return render_template('rubric_verify.html',
            parsed_rubric=parsed,
            rubric_json=rubric_json_b64,
            rubric_filename=rubric_filename,
            submission_folder=submission_folder,
            context_path=context_path
        )
    else:
        # Using a saved rubric; skip verification, go straight to grading 
        rubric_data = load_rubric(rubric_choice)
        
        if 'error' in rubric_data:
            flash(f'Could not load rubric: {rubric_data["error"]}', 'error')
            return redirect(url_for('upload.upload_page'))
        
        # Grade the report using two-stage pipeline
        grading_result = grade_report(result['text'], rubric_data)
        
        if 'error' in grading_result:
            flash(f'Grading failed: {grading_result["error"]}', 'error')
            return redirect(url_for('upload.upload_page'))
        
        # # Storing results in session for the results page 
        # session['grading_result'] = grading_result
        # session['student_info'] = {
        #     'name': student_name,
        #     'number': student_number,
        #     'report_filename': report_filename,
        #     'submission_folder': submission_folder
        # }

        # Saving results to file as session cookies are too small
        results_data = {
            'grading_result': grading_result,
            'student_info': {
                'name': student_name,
                'number': student_number,
                'report_filename': report_filename,
                'submission_folder': submission_folder
            }
        }
        
        results_path = os.path.join(submission_folder, 'grading_results.json')
        with open(results_path, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        session['results_path'] = results_path
        
        return redirect(url_for('grading.grading_page'))

@upload_bp.route('/rubric/confirm', methods=['POST'])
def confirm_rubric():
    """
    Handle rubric confirmation.
    Saves the rubric, then continues to grading 
    """
    rubric_data = request.form.get('rubric_data')
    rubric_filename = request.form.get('rubric_filename')
    submission_folder = request.form.get('submission_folder')
    context_path = request.form.get('context_path')
    
    if not rubric_data:
        flash('No rubric data received.', 'error')
        return redirect(url_for('upload.upload_page'))
    
    try:
        decoded = base64.b64decode(rubric_data.encode()).decode()
        parsed_rubric = json.loads(decoded)
    except Exception:
        flash('Invalid rubric data.', 'error')
        return redirect(url_for('upload.upload_page'))
    
    # Save the parsed rubric as JSON 
    saved_filename = save_rubric(parsed_rubric, rubric_filename)
    
    flash(f'Rubric "{parsed_rubric.get("rubric_name", "Unknown")}" saved successfully!', 'success')
    
    # If we have report context, continue straight to grading
    if context_path and os.path.exists(context_path):
        with open(context_path, 'r') as f:
            context = json.load(f)
        
        report_text = context['report_text']
        student_info = context['student_info']
        
        # Grade the report
        grading_result = grade_report(report_text, parsed_rubric)
        
        if 'error' in grading_result:
            flash(f'Grading failed: {grading_result["error"]}', 'error')
            return redirect(url_for('upload.upload_page'))
        
        # Save results
        results_data = {
            'grading_result': grading_result,
            'student_info': student_info
        }
        
        results_path = os.path.join(submission_folder, 'grading_results.json')
        with open(results_path, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        session['results_path'] = results_path
        
        # Clean up temp file
        os.remove(context_path)
        
        return redirect(url_for('grading.grading_page'))
    
    # No report context; just go back to upload
    return redirect(url_for('upload.upload_page'))