"""
Unit Tests for Upload Validation
---------------------------------
Tests the validation functions used in the upload route.
"""

import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.upload import allowed_file
import config


class TestAllowedFile:
    """Tests for the allowed_file() function."""

    def test_valid_pdf(self):
        """PDF files should be allowed for reports."""
        assert allowed_file('report.pdf', config.ALLOWED_REPORT_EXTENSIONS) == True

    def test_valid_docx(self):
        """DOCX files should be allowed for reports."""
        assert allowed_file('report.docx', config.ALLOWED_REPORT_EXTENSIONS) == True

    def test_invalid_txt(self):
        """TXT files should NOT be allowed."""
        assert allowed_file('report.txt', config.ALLOWED_REPORT_EXTENSIONS) == False

    def test_invalid_exe(self):
        """EXE files should NOT be allowed."""
        assert allowed_file('malware.exe', config.ALLOWED_REPORT_EXTENSIONS) == False

    def test_no_extension(self):
        """Files with no extension should NOT be allowed."""
        assert allowed_file('report', config.ALLOWED_REPORT_EXTENSIONS) == False

    def test_uppercase_extension(self):
        """Should handle uppercase extensions like .PDF."""
        assert allowed_file('report.PDF', config.ALLOWED_REPORT_EXTENSIONS) == True

    def test_mixed_case_extension(self):
        """Should handle mixed case like .Pdf."""
        assert allowed_file('report.Pdf', config.ALLOWED_REPORT_EXTENSIONS) == True

    def test_double_extension(self):
        """Should check only the last extension."""
        # 'report.txt.pdf' should be allowed — last extension is .pdf
        assert allowed_file('report.txt.pdf', config.ALLOWED_REPORT_EXTENSIONS) == True

    def test_rubric_pdf_only(self):
        """Rubric uploads should only accept PDF."""
        assert allowed_file('rubric.pdf', config.ALLOWED_RUBRIC_EXTENSIONS) == True
        assert allowed_file('rubric.docx', config.ALLOWED_RUBRIC_EXTENSIONS) == False

    def test_empty_filename(self):
        """Empty filename should NOT be allowed."""
        assert allowed_file('', config.ALLOWED_REPORT_EXTENSIONS) == False


class TestStudentNumberValidation:
    """Tests for student number format validation (UP + 7 digits)."""

    def test_valid_uppercase(self):
        """UP2303086 should be valid."""
        assert re.match(r'^UP\d{7}$', 'UP2303086') is not None

    def test_valid_after_upper(self):
        """up2303086 uppercased to UP2303086 should be valid."""
        number = 'up2303086'.upper()
        assert re.match(r'^UP\d{7}$', number) is not None

    def test_too_short(self):
        """UP230308 (6 digits) should be invalid."""
        assert re.match(r'^UP\d{7}$', 'UP230308') is None

    def test_too_long(self):
        """UP23030861 (8 digits) should be invalid."""
        assert re.match(r'^UP\d{7}$', 'UP23030861') is None

    def test_no_prefix(self):
        """2303086 (no UP prefix) should be invalid."""
        assert re.match(r'^UP\d{7}$', '2303086') is None

    def test_wrong_prefix(self):
        """AB2303086 should be invalid."""
        assert re.match(r'^UP\d{7}$', 'AB2303086') is None

    def test_letters_in_digits(self):
        """UP230ABC6 should be invalid."""
        assert re.match(r'^UP\d{7}$', 'UP230ABC6') is None

    def test_empty_string(self):
        """Empty string should be invalid."""
        assert re.match(r'^UP\d{7}$', '') is None