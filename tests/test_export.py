"""
Unit Tests for Export Service
------------------------------
Tests PDF and Excel export generation.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.export import export_to_excel, export_to_pdf


class TestExcelExport:
    """Tests for Excel export."""

    def _make_test_data(self):
        """Create minimal test data for export."""
        return {
            'student_info': {
                'name': 'Test Student',
                'number': 'UP1234567',
                'report_filename': 'test_report.pdf',
                'submission_folder': '/tmp/test'
            },
            'grading_result': {
                'overall_score': 65.5,
                'overall_grade_band': '60-69',
                'overall_summary': 'This is a test summary.',
                'plagiarism_flags': 'None detected',
                'marker_reviewed': False,
                'criteria_results': [
                    {
                        'criterion_name': 'Test Criterion',
                        'weighting': 100,
                        'score': 65,
                        'grade_band': '60-69',
                        'feedback': 'Test feedback.',
                        'evidence_location': 'Chapter 1'
                    }
                ]
            }
        }

    def test_excel_creates_file(self):
        """Excel export should create a .xlsx file."""
        data = self._make_test_data()
        # tempfile creates a temporary file that gets cleaned up automatically
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            output_path = f.name

        try:
            result = export_to_excel(data, output_path)
            assert result.get('success') == True
            assert os.path.exists(output_path)
            # Check file is not empty
            assert os.path.getsize(output_path) > 0
        finally:
            # Clean up the temp file
            if os.path.exists(output_path):
                os.remove(output_path)

    def test_excel_handles_missing_fields(self):
        """Excel export should handle missing optional fields gracefully."""
        data = self._make_test_data()
        # Remove optional fields
        del data['grading_result']['plagiarism_flags']
        del data['grading_result']['marker_reviewed']

        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            output_path = f.name

        try:
            result = export_to_excel(data, output_path)
            assert result.get('success') == True
        finally:
            if os.path.exists(output_path):
                os.remove(output_path)


class TestPDFExport:
    """Tests for PDF export."""

    def _make_test_data(self):
        """Create minimal test data for export."""
        return {
            'student_info': {
                'name': 'Test Student',
                'number': 'UP1234567',
                'report_filename': 'test_report.pdf',
                'submission_folder': '/tmp/test'
            },
            'grading_result': {
                'overall_score': 72.3,
                'overall_grade_band': '70-79',
                'overall_summary': 'Good work overall.',
                'plagiarism_flags': 'None detected',
                'criteria_results': [
                    {
                        'criterion_name': 'Test Criterion',
                        'weighting': 100,
                        'score': 72,
                        'grade_band': '70-79',
                        'feedback': 'Well done.',
                        'evidence_location': 'Chapter 2'
                    }
                ]
            }
        }

    def test_pdf_creates_file(self):
        """PDF export should create a .pdf file."""
        data = self._make_test_data()
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            output_path = f.name

        try:
            result = export_to_pdf(data, output_path)
            assert result.get('success') == True
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
        finally:
            if os.path.exists(output_path):
                os.remove(output_path)

    def test_pdf_handles_empty_feedback(self):
        """PDF export should handle empty feedback without crashing."""
        data = self._make_test_data()
        data['grading_result']['criteria_results'][0]['feedback'] = ''
        data['grading_result']['criteria_results'][0]['evidence_location'] = ''

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            output_path = f.name

        try:
            result = export_to_pdf(data, output_path)
            assert result.get('success') == True
        finally:
            if os.path.exists(output_path):
                os.remove(output_path)