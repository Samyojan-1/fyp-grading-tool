"""
Tests for Bulk (Batch) Grading
------------------------------
Covers the filename parser (pure function, no AI needed) and the
batch routes using Flask's test client. No test here calls the AI.
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from services.batch_grader import parse_student_filename, is_valid_batch_id


class TestFilenameParser:
    """Tests for extracting student details from report filenames."""

    def test_standard_filename(self):
        """The common shape: grade_course_First_Last_UPnumber.pdf"""
        result = parse_student_filename('65_DSA_Benjamin_West_UP2113294.pdf')
        assert result['student_number'] == 'UP2113294'
        assert result['student_name'] == 'Benjamin West'
        assert result['flags'] == []

    def test_double_underscore(self):
        """Some files have double underscores after the course code."""
        result = parse_student_filename('68_CMP__Xinran_Yang_UP2295431.docx')
        assert result['student_number'] == 'UP2295431'
        assert result['student_name'] == 'Xinran Yang'

    def test_no_separator_before_course_code(self):
        """e.g. 42CSFC_George_Longhurst_UP2071779.docx"""
        result = parse_student_filename('42CSFC_George_Longhurst_UP2071779.docx')
        assert result['student_number'] == 'UP2071779'
        assert result['student_name'] == 'George Longhurst'

    def test_hyphenated_surname(self):
        result = parse_student_filename('78_CS_Harry_Spencer-Whitcombe_UP2052662.docx')
        assert result['student_number'] == 'UP2052662'
        assert result['student_name'] == 'Harry Spencer-Whitcombe'

    def test_lowercase_up_number(self):
        """UP numbers should be normalised to uppercase."""
        result = parse_student_filename('40_CS_Vilius_Slicius_up2018318.pdf')
        assert result['student_number'] == 'UP2018318'

    def test_missing_up_number_is_flagged(self):
        """No UP number: still parses a name, but adds a warning flag."""
        result = parse_student_filename('55_SE_Jane_Smith.pdf')
        assert result['student_number'] == ''
        assert result['student_name'] == 'Jane Smith'
        assert len(result['flags']) == 1
        assert 'UP student number' in result['flags'][0]

    def test_unparseable_filename_falls_back_to_stem(self):
        """A filename with nothing usable falls back to the filename itself."""
        result = parse_student_filename('FINAL_REPORT.pdf')
        assert result['student_number'] == ''
        assert result['student_name'] == 'FINAL_REPORT'
        assert len(result['flags']) == 2  # no number AND no name found

    def test_only_up_number(self):
        """Just a UP number: number found, name flagged."""
        result = parse_student_filename('UP2113294.pdf')
        assert result['student_number'] == 'UP2113294'
        assert any('name' in flag for flag in result['flags'])


class TestBatchIdValidation:
    """Batch ids come from URLs, so they must be strictly validated."""

    def test_valid_batch_id(self):
        assert is_valid_batch_id('batch_20260708_143210')

    def test_path_traversal_rejected(self):
        assert not is_valid_batch_id('../../etc/passwd')
        assert not is_valid_batch_id('batch_20260708/../..')

    def test_empty_and_none_rejected(self):
        assert not is_valid_batch_id('')
        assert not is_valid_batch_id(None)


class TestBatchRoutes:
    """Tests for the bulk upload and batch status routes."""

    def setup_method(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_bulk_page_loads(self):
        response = self.client.get('/bulk')
        assert response.status_code == 200

    def test_bulk_page_has_multiple_file_input(self):
        response = self.client.get('/bulk')
        html = response.data.decode()
        # Either the form (rubrics saved) or the warning (none saved)
        assert 'multiple' in html or 'No saved rubrics' in html

    def test_bulk_upload_without_files_redirects(self):
        """Submitting with a rubric but no files should show an error."""
        response = self.client.post('/bulk-upload', data={
            'rubric_choice': 'nonexistent_rubric.json'
        }, follow_redirects=True)
        html = response.data.decode()
        assert 'Could not load rubric' in html or 'at least one report' in html

    def test_bulk_upload_without_rubric_redirects(self):
        response = self.client.post('/bulk-upload', data={},
                                    follow_redirects=True)
        html = response.data.decode()
        assert 'rubric' in html.lower()

    def test_unknown_batch_page_redirects(self):
        response = self.client.get('/batch/batch_00000000_000000',
                                   follow_redirects=True)
        html = response.data.decode()
        assert 'Batch not found' in html

    def test_unknown_batch_status_returns_404(self):
        response = self.client.get('/batch/batch_00000000_000000/status')
        assert response.status_code == 404

    def test_invalid_batch_id_status_returns_404(self):
        """A malicious batch id in the URL must not reach the filesystem."""
        response = self.client.get('/batch/notabatch/status')
        assert response.status_code == 404

    def test_navbar_has_bulk_link(self):
        response = self.client.get('/')
        html = response.data.decode()
        assert 'Bulk upload' in html
