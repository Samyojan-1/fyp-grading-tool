import os
import re
from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for
from werkzeug.utils import secure_filename
import config
from services.file_parser import extract_text

upload_bp = Blueprint('upload', __name__)


def get_saved_rubrics():
    """Get a list of previously saved rubric JSON files from the rubrics folder."""
    rubric_folder = config.RUBRIC_FOLDER
    if not os.path.exists(rubric_folder):
        os.makedirs(rubric_folder)
        return []
    # List all .json files in the rubrics folder
    return [f for f in os.listdir(rubric_folder) if f.endswith('.json')]


def allowed_file(filename, allowed_extensions):
    """
    Check if a filename has an allowed extension.
    
    How it works:
    1. '.' in filename — makes sure there IS an extension (no dot = no extension)
    2. filename.rsplit('.', 1) — splits from the RIGHT, once. 
       'report.pdf' becomes ['report', 'pdf']
       'my.report.v2.pdf' becomes ['my.report.v2', 'pdf']  (only splits the last dot)
    3. [1].lower() — takes the extension part and lowercases it
    4. Checks if it's in the allowed set
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


@upload_bp.route('/')
def upload_page():
    """Show the upload form."""
    saved_rubrics = get_saved_rubrics()
    return render_template('upload.html', saved_rubrics=saved_rubrics)


@upload_bp.route('/upload', methods=['POST'])
def handle_upload():
    """
    Handle the form submission.
    This runs when the user clicks 'Start Grading'.
    
    request.files — contains uploaded files
    request.form — contains text fields (like student_name)
    """
    
    # --- Get student details ---
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
    # ^UP\d{7}$ means: starts with UP, then exactly 7 digits, then end of string
    # ^ = start, $ = end, \d = any digit, {7} = exactly 7 times
    if not re.match(r'^UP\d{7}$', student_number):
        flash('Invalid student number. Must be UP followed by 7 digits (e.g. UP2303086).', 'error')
        return redirect(url_for('upload.upload_page'))
    
    # --- Validate the report file ---
    # request.files['report'] gets the file from the form input named "report"
    if 'report' not in request.files:
        flash('No report file uploaded.', 'error')
        return redirect(url_for('upload.upload_page'))
    
    report_file = request.files['report']
    
    # This can happen if user submits form without selecting a file
    if report_file.filename == '':
        flash('No report file selected.', 'error')
        return redirect(url_for('upload.upload_page'))
    
    if not allowed_file(report_file.filename, config.ALLOWED_REPORT_EXTENSIONS):
        flash('Invalid report format. Please upload a PDF or DOCX file.', 'error')
        return redirect(url_for('upload.upload_page'))
    
    # --- Handle rubric ---
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
    
    # --- Create submission folder (FR-31) ---
    # Format: UP2303086_SamDev_2026-04-02
    # Student number first (what teachers care about), then name (human readable), then date
    date_str = datetime.now().strftime('%Y-%m-%d')
    folder_name = f"{student_number}_{secure_filename(student_name)}_{date_str}"
    submission_folder = os.path.join(config.UPLOAD_FOLDER, folder_name)
    os.makedirs(submission_folder, exist_ok=True)
    
    # --- Save the report ---
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
    
    # Check if extraction failed
    if 'error' in result:
        flash(f'Warning: Could not extract text from report — {result["error"]}', 'error')
        return redirect(url_for('upload.upload_page'))
    
    # Check for scanned PDF (FR-04)
    if result.get('is_scanned'):
        flash('Warning: This PDF appears to be scanned (no extractable text). '
              'It has been flagged for manual review.', 'error')
        return redirect(url_for('upload.upload_page'))
    
    # For now, let's just print the stats to the terminal so we can verify it works
    # We'll use this data properly in Phase 3+
    print(f"\n{'='*50}")
    print(f"Text extracted from: {report_filename}")
    print(f"Total characters: {len(result['text'])}")
    if 'page_count' in result:
        print(f"Pages: {result['page_count']}")
    if 'paragraph_count' in result:
        print(f"Paragraphs: {result['paragraph_count']}")
    # Show first 500 characters as a preview
    print(f"\nPreview:\n{result['text'][:500]}")
    print(f"{'='*50}\n")
    
    # Success!
    flash(f'Files uploaded successfully for {student_name} ({student_number})!', 'success')
    
    # For now, redirect back to upload page
    # Later this will redirect to the grading page
    return redirect(url_for('upload.upload_page'))