"""
Batch (bulk upload) Routes
--------------------------
Handles the bulk upload page, starting a batch grading job, and the
progress/summary page that polls for status while grading runs in the
background.
"""

import os
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
import config
from routes.upload import get_saved_rubrics, allowed_file
from services.rubric_parser import load_rubric
from services import batch_grader

batch_bp = Blueprint('batch', __name__)


@batch_bp.route('/bulk')
def bulk_page():
    # The bulk page only offers SAVED rubrics — parsing a new rubric needs
    # the interactive verification step, which doesn't fit a hands-off batch.
    saved_rubrics = get_saved_rubrics()
    return render_template('bulk_upload.html', saved_rubrics=saved_rubrics)


@batch_bp.route('/bulk-upload', methods=['POST'])
def handle_bulk_upload():
    """
    Runs when the user clicks 'Start batch grading'.
    Only does the quick work (validate + save files), then hands grading
    to a background thread and redirects to the progress page.
    """
    # -- Validate the rubric choice --
    rubric_choice = request.form.get('rubric_choice', '')

    if not rubric_choice:
        flash('Please select a saved rubric.', 'error')
        return redirect(url_for('batch.bulk_page'))

    rubric_data = load_rubric(rubric_choice)
    if 'error' in rubric_data:
        flash(f'Could not load rubric: {rubric_data["error"]}', 'error')
        return redirect(url_for('batch.bulk_page'))

    # -- Validate the report files --
    # getlist() returns ALL files from a multiple-file input
    files = [f for f in request.files.getlist('reports') if f and f.filename]

    if not files:
        flash('Please select at least one report file.', 'error')
        return redirect(url_for('batch.bulk_page'))

    valid_files = []
    skipped = []
    for f in files:
        if allowed_file(f.filename, config.ALLOWED_REPORT_EXTENSIONS):
            valid_files.append(f)
        else:
            skipped.append(f.filename)

    if not valid_files:
        flash('None of the selected files are PDF or DOCX.', 'error')
        return redirect(url_for('batch.bulk_page'))

    if skipped:
        flash(f'Skipped {len(skipped)} file(s) with unsupported format: '
              f'{", ".join(skipped)}', 'error')

    # -- Create the batch and start grading in the background --
    status = batch_grader.create_batch(
        valid_files,
        rubric_filename=rubric_choice,
        rubric_name=rubric_data.get('rubric_name', rubric_choice),
    )
    batch_grader.start_batch(status['batch_id'])

    flash(f'Batch started: {len(valid_files)} report(s) queued for grading.', 'success')
    return redirect(url_for('batch.batch_page', batch_id=status['batch_id']))


@batch_bp.route('/batch/<batch_id>')
def batch_page(batch_id):
    # The progress/summary page. It renders once, then JavaScript polls
    # the /status endpoint below to keep itself up to date.
    status = batch_grader.load_status(batch_id)
    if status is None:
        flash('Batch not found.', 'error')
        return redirect(url_for('batch.bulk_page'))
    return render_template('batch_progress.html', status=status)


@batch_bp.route('/batch/<batch_id>/status')
def batch_status(batch_id):
    """
    JSON endpoint the progress page polls every few seconds.
    Returns the current state of every report plus overall counts.
    """
    status = batch_grader.load_status(batch_id)
    if status is None:
        return jsonify({'error': 'Batch not found'}), 404

    reports = []
    for entry in status['reports']:
        report = {
            'index': entry['index'],
            'filename': entry['filename'],
            'student_name': entry['student_name'],
            'student_number': entry['student_number'],
            'status': entry['status'],
            'flags': entry['flags'],
            'error': entry['error'],
            'overall_score': entry['overall_score'],
            'overall_grade_band': entry['overall_grade_band'],
            'view_url': None,
        }
        if entry['status'] == 'done':
            report['view_url'] = url_for('grading.grading_page',
                                         batch=batch_id, report=entry['index'])
        reports.append(report)

    counts = {
        'total': len(reports),
        'done': sum(1 for r in reports if r['status'] == 'done'),
        'flagged': sum(1 for r in reports if r['status'] == 'flagged'),
        'failed': sum(1 for r in reports if r['status'] == 'failed'),
        'pending': sum(1 for r in reports if r['status'] in ('pending', 'grading')),
    }

    return jsonify({
        'batch_id': status['batch_id'],
        'rubric_name': status['rubric_name'],
        'created': status['created'],
        'running': batch_grader.is_running(batch_id),
        'counts': counts,
        'reports': reports,
    })


@batch_bp.route('/batch/<batch_id>/resume', methods=['POST'])
def resume_batch(batch_id):
    """
    Restart grading for a batch. Used for:
    - Retrying a single failed report (report_index in the form data)
    - Resuming a batch that was interrupted by a server restart
    """
    status = batch_grader.load_status(batch_id)
    if status is None:
        return jsonify({'error': 'Batch not found'}), 404

    # If retrying one specific report, reset it to pending first
    report_index = request.form.get('report_index')
    if report_index is not None and report_index != '':
        try:
            index = int(report_index)
            entry = status['reports'][index]
        except (ValueError, IndexError):
            return jsonify({'error': 'Invalid report index'}), 400

        if entry['status'] == 'failed':
            batch_grader.update_report(batch_id, index, {
                'status': 'pending',
                'error': None,
            })

    started = batch_grader.start_batch(batch_id)
    return jsonify({'started': started, 'running': True})
