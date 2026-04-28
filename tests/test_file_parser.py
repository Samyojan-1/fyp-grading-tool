"""
Unit Tests for File Parser Service
-----------------------------------
Tests the text extraction functions for PDF and DOCX files.

How pytest works:
- Each function starting with 'test_' is a test case
- 'assert' checks if something is True — if not, the test fails
- pytest discovers and runs all test files automatically
- Run with: pytest tests/ -v  (the -v flag shows verbose output)
"""

import os
import sys

# Add the project root to Python's path so we can import our modules
# Without this, Python can't find 'services.file_parser'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.file_parser import extract_text, extract_text_from_pdf, extract_text_from_docx


class TestExtractText:
    """Tests for the extract_text() facade function."""

    def test_unsupported_file_type(self):
        """extract_text should return an error for unsupported file types."""
        result = extract_text('report.txt')
        # We expect an error key in the result
        assert 'error' in result
        assert 'Unsupported file type' in result['error']

    def test_pdf_file_detection(self):
        """extract_text should detect .pdf files and route to PDF extractor."""
        # This will fail because the file doesn't exist,
        # but it tests that the function TRIES to open it as a PDF
        result = extract_text('nonexistent.pdf')
        assert 'error' in result
        assert 'Failed to parse PDF' in result['error']

    def test_docx_file_detection(self):
        """extract_text should detect .docx files and route to DOCX extractor."""
        result = extract_text('nonexistent.docx')
        assert 'error' in result

    def test_case_insensitive_extension(self):
        """extract_text should handle uppercase extensions like .PDF."""
        result = extract_text('report.PDF')
        # Should try PDF extraction, not return 'unsupported'
        assert 'Unsupported file type' not in result.get('error', '')


class TestPDFExtraction:
    """Tests for PDF-specific extraction."""

    def test_nonexistent_pdf(self):
        """Should return an error for a file that doesn't exist."""
        result = extract_text_from_pdf('/nonexistent/path/report.pdf')
        assert 'error' in result
        assert result['text'] == ''
        assert result['page_count'] == 0

    def test_pdf_returns_expected_keys(self):
        """PDF extraction result should always have these keys."""
        result = extract_text_from_pdf('/nonexistent/path/report.pdf')
        # Even on failure, all keys should be present
        assert 'text' in result
        assert 'pages' in result
        assert 'page_count' in result
        assert 'is_scanned' in result


class TestDOCXExtraction:
    """Tests for DOCX-specific extraction."""

    def test_nonexistent_docx(self):
        """Should return an error for a file that doesn't exist."""
        result = extract_text_from_docx('/nonexistent/path/report.docx')
        assert 'error' in result
        assert result['text'] == ''

    def test_docx_returns_expected_keys(self):
        """DOCX extraction result should always have these keys."""
        result = extract_text_from_docx('/nonexistent/path/report.docx')
        assert 'text' in result
        assert 'paragraphs' in result
        assert 'paragraph_count' in result
        assert 'is_scanned' in result