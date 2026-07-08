"""
Bulk (batch) grading service.
-----------------------------
Grades many reports against one rubric in the background.

How it works:
1. create_batch() saves the uploaded files into uploads/batch_<timestamp>/
   (one sub-folder per report, mirroring the single-upload layout) and
   writes a batch_status.json file listing every report as "pending".
2. start_batch() launches a background thread, so the web request can
   return immediately and the user gets redirected to a progress page.
3. The background thread grades reports through the SAME pipeline as a
   single upload (extract_text -> grade_report), a few at a time using
   a thread pool. After each report it updates batch_status.json, which
   the progress page polls to show "Graded 7 of 25".

One bad report (scanned PDF, corrupt file, AI error) never stops the
batch — it just gets marked as flagged/failed and the rest continue.
"""

import os
import re
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from werkzeug.utils import secure_filename
import config
from services.file_parser import extract_text
from services.rubric_parser import load_rubric
from services.ai_grader import grade_report

STATUS_FILENAME = 'batch_status.json'

# A lock makes sure two worker threads never write batch_status.json at
# the same time (which would corrupt the file).
STATUS_LOCK = threading.Lock()

# Batches currently being graded by THIS server process.
# If the server restarts mid-batch, this empties — the progress page
# then offers a "Resume" button which calls start_batch() again.
ACTIVE_BATCHES = set()
ACTIVE_LOCK = threading.Lock()


def parse_student_filename(filename):
    """
    Pull the student name and UP number out of a report filename.

    Filenames typically look like: 65_DSA_Benjamin_West_UP2113294.pdf
    (grade prefix, course code, name parts, UP number)

    Returns a dict with student_name, student_number and a list of
    flags for anything that could not be worked out — the report is
    still graded, the marker just gets warned to check it manually.
    """
    stem = os.path.splitext(os.path.basename(filename))[0]
    flags = []

    # Find the UP number anywhere in the filename
    match = re.search(r'UP\d{7}', stem, re.IGNORECASE)
    if match:
        student_number = match.group(0).upper()
        # Remove the UP number so it doesn't end up in the name
        name_part = stem[:match.start()] + stem[match.end():]
    else:
        student_number = ''
        name_part = stem
        flags.append('Could not find a UP student number in the filename — check manually.')

    # Split on underscores and drop leading tokens that look like codes
    # (e.g. "65", "DSA", "42CSFC") — real name parts are mixed case.
    tokens = [t for t in name_part.split('_') if t]
    name_tokens = []
    for token in tokens:
        if not name_tokens and re.fullmatch(r'[A-Z0-9]{1,6}', token):
            continue
        name_tokens.append(token)

    student_name = ' '.join(name_tokens).strip()
    if not student_name:
        student_name = stem
        flags.append('Could not read a student name from the filename — using the filename instead.')

    return {
        'student_name': student_name,
        'student_number': student_number,
        'flags': flags,
    }


def is_valid_batch_id(batch_id):
    # Batch ids come from URLs, so validate the format strictly to stop
    # anyone sneaking in a path like "../../secrets".
    return bool(re.fullmatch(r'batch_[0-9_]+', batch_id or ''))


def batch_folder_path(batch_id):
    return os.path.join(config.UPLOAD_FOLDER, batch_id)


def load_status(batch_id):
    """Load batch_status.json for a batch. Returns None if not found."""
    if not is_valid_batch_id(batch_id):
        return None
    status_path = os.path.join(batch_folder_path(batch_id), STATUS_FILENAME)
    if not os.path.exists(status_path):
        return None
    with open(status_path, 'r') as f:
        return json.load(f)


def save_status(status):
    """
    Write batch_status.json atomically: write to a temp file first, then
    swap it into place. A reader can never see a half-written file.
    """
    status_path = os.path.join(batch_folder_path(status['batch_id']), STATUS_FILENAME)
    tmp_path = status_path + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(status, f, indent=2)
    os.replace(tmp_path, status_path)


def update_report(batch_id, index, updates):
    """Update one report's entry in batch_status.json (thread-safe)."""
    with STATUS_LOCK:
        status = load_status(batch_id)
        if status is None:
            return
        status['reports'][index].update(updates)
        save_status(status)


def is_running(batch_id):
    with ACTIVE_LOCK:
        return batch_id in ACTIVE_BATCHES


def create_batch(files, rubric_filename, rubric_name):
    """
    Save the uploaded files and create the batch status record.
    Only does fast disk work — no AI calls — so the request returns quickly.
    Returns the status dict (including the new batch_id).
    """
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

    # Batch id from the timestamp, e.g. batch_20260708_1432_00
    batch_id = 'batch_' + datetime.now().strftime('%Y%m%d_%H%M%S')
    counter = 1
    while os.path.exists(batch_folder_path(batch_id)):
        counter += 1
        batch_id = batch_id.split('__')[0] + f'__{counter}'
    batch_folder = batch_folder_path(batch_id)
    os.makedirs(batch_folder)

    reports = []
    for i, file in enumerate(files):
        safe_name = secure_filename(file.filename)
        info = parse_student_filename(file.filename)

        # One folder per report, same idea as the single-upload flow:
        # UP2113294_Benjamin_West/
        if info['student_number']:
            folder_base = f"{info['student_number']}_{secure_filename(info['student_name'])}"
        else:
            folder_base = os.path.splitext(safe_name)[0] or f'report_{i}'

        report_folder = os.path.join(batch_folder, folder_base)
        suffix = 1
        while os.path.exists(report_folder):
            suffix += 1
            report_folder = os.path.join(batch_folder, f'{folder_base}_{suffix}')
        os.makedirs(report_folder)

        file.save(os.path.join(report_folder, safe_name))

        reports.append({
            'index': i,
            'filename': safe_name,
            'student_name': info['student_name'],
            'student_number': info['student_number'],
            'folder': report_folder,
            'status': 'pending',   # pending -> grading -> done / flagged / failed
            'flags': info['flags'],
            'error': None,
            'overall_score': None,
            'overall_grade_band': None,
        })

    status = {
        'batch_id': batch_id,
        'rubric_filename': rubric_filename,
        'rubric_name': rubric_name,
        'created': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'reports': reports,
    }
    save_status(status)
    return status


def start_batch(batch_id):
    """
    Start grading a batch in a background thread.
    Returns True if started, False if this batch is already running.
    """
    with ACTIVE_LOCK:
        if batch_id in ACTIVE_BATCHES:
            return False
        ACTIVE_BATCHES.add(batch_id)

    # daemon=True means the thread won't stop the server shutting down
    thread = threading.Thread(target=run_batch, args=(batch_id,), daemon=True)
    thread.start()
    return True


def run_batch(batch_id):
    """
    The background job: grade every pending report in the batch.
    Runs MAX_PARALLEL_REPORTS reports at once — the limit is Azure's
    rate limits, not Flask, so keep this small (2-3).
    """
    try:
        status = load_status(batch_id)
        if status is None:
            return

        rubric_data = load_rubric(status['rubric_filename'])
        if 'error' in rubric_data:
            # Can't grade anything without a rubric — fail all pending reports
            for entry in status['reports']:
                if entry['status'] in ('pending', 'grading'):
                    update_report(batch_id, entry['index'], {
                        'status': 'failed',
                        'error': f"Could not load rubric: {rubric_data['error']}",
                    })
            return

        # Reports stuck in "grading" can only be leftovers from a crashed
        # or restarted server (only one run per batch is allowed), so
        # reset them to pending and pick them up again.
        pending_indexes = []
        for entry in status['reports']:
            if entry['status'] in ('pending', 'grading'):
                if entry['status'] == 'grading':
                    update_report(batch_id, entry['index'], {'status': 'pending'})
                pending_indexes.append(entry['index'])

        with ThreadPoolExecutor(max_workers=config.MAX_PARALLEL_REPORTS) as pool:
            futures = [
                pool.submit(grade_one_report, batch_id, index, rubric_data)
                for index in pending_indexes
            ]
            # Wait for all of them to finish
            for future in futures:
                future.result()
    finally:
        # Always clear the "running" marker, even if something crashed
        with ACTIVE_LOCK:
            ACTIVE_BATCHES.discard(batch_id)


def grade_one_report(batch_id, index, rubric_data):
    """
    Grade a single report inside the batch. Any problem marks THIS report
    as flagged/failed and returns — it never raises, so the rest of the
    batch always carries on.
    """
    status = load_status(batch_id)
    entry = status['reports'][index]
    update_report(batch_id, index, {'status': 'grading'})

    try:
        report_path = os.path.join(entry['folder'], entry['filename'])

        # Step 1: extract text (same as single upload)
        extraction = extract_text(report_path)

        if 'error' in extraction:
            update_report(batch_id, index, {
                'status': 'failed',
                'error': f"Could not read file: {extraction['error']}",
            })
            return

        if extraction.get('is_scanned'):
            update_report(batch_id, index, {
                'status': 'flagged',
                'flags': entry['flags'] + [
                    'Scanned PDF — no extractable text. Needs manual grading.'
                ],
            })
            return

        # Step 2: grade through the existing two-stage pipeline
        grading_result = grade_report(extraction['text'], rubric_data)

        if 'error' in grading_result:
            update_report(batch_id, index, {
                'status': 'failed',
                'error': grading_result['error'],
            })
            return

        # Step 3: save results in the SAME format as the single-upload
        # flow, so the existing results page, editing and export all work.
        results_data = {
            'grading_result': grading_result,
            'student_info': {
                'name': entry['student_name'],
                'number': entry['student_number'],
                'report_filename': entry['filename'],
                'submission_folder': entry['folder'],
            },
        }
        results_path = os.path.join(entry['folder'], 'grading_results.json')
        with open(results_path, 'w') as f:
            json.dump(results_data, f, indent=2)

        update_report(batch_id, index, {
            'status': 'done',
            'overall_score': grading_result.get('overall_score'),
            'overall_grade_band': grading_result.get('overall_grade_band'),
        })

    except Exception as e:
        # Catch-all so an unexpected crash in one report can't kill the batch
        update_report(batch_id, index, {
            'status': 'failed',
            'error': f'Unexpected error: {str(e)}',
        })
