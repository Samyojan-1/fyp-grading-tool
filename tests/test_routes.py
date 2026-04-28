"""
Integration Tests for Flask Routes
------------------------------------
Tests that the Flask routes respond correctly.

These use Flask's built-in test client — it simulates HTTP requests
without needing to start the actual server. This means we can test
routes quickly without a browser.
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app


class TestUploadRoutes:
    """Tests for the upload page and form submission."""

    def setup_method(self):
        """
        Runs before EACH test method.
        
        app.test_client() creates a fake browser that can make requests
        to our Flask app without starting the server.
        """
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_upload_page_loads(self):
        """The upload page should return 200 OK."""
        response = self.client.get('/')
        assert response.status_code == 200

    def test_upload_page_has_form(self):
        """The upload page should contain the upload form."""
        response = self.client.get('/')
        html = response.data.decode()
        assert 'enctype="multipart/form-data"' in html
        assert 'student_name' in html
        assert 'student_number' in html
        assert 'Start grading' in html

    def test_upload_page_shows_saved_rubrics(self):
        """The upload page should have the rubric dropdown."""
        response = self.client.get('/')
        html = response.data.decode()
        assert 'rubric_choice' in html
        assert 'Upload new rubric' in html

    def test_upload_no_file_redirects(self):
        """Submitting the form without a file should redirect back."""
        response = self.client.post('/upload', data={
            'student_name': 'Test Student',
            'student_number': 'UP1234567',
            'rubric_choice': 'upload_new'
        }, follow_redirects=True)
        html = response.data.decode()
        # Should show an error message
        assert 'No report file' in html or 'report' in html.lower()

    def test_upload_invalid_student_number(self):
        """Submitting with an invalid student number should show an error."""
        response = self.client.post('/upload', data={
            'student_name': 'Test Student',
            'student_number': 'INVALID',
            'rubric_choice': 'upload_new'
        }, follow_redirects=True)
        html = response.data.decode()
        assert 'Invalid student number' in html or 'UP followed by 7 digits' in html

    def test_upload_empty_name(self):
        """Submitting with an empty name should show an error."""
        response = self.client.post('/upload', data={
            'student_name': '',
            'student_number': 'UP1234567',
            'rubric_choice': 'upload_new'
        }, follow_redirects=True)
        html = response.data.decode()
        assert 'student name' in html.lower()


class TestGradingRoutes:
    """Tests for the grading/results routes."""

    def setup_method(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_grading_page_without_results_redirects(self):
        """Visiting /grading with no results should redirect to upload."""
        response = self.client.get('/grading', follow_redirects=True)
        html = response.data.decode()
        # Should redirect to upload page with a message
        assert 'Upload' in html
        assert 'No grading results' in html or 'upload' in html.lower()

    def test_grading_export_without_results_redirects(self):
        """Exporting without results should redirect to upload."""
        response = self.client.get('/grading/export', follow_redirects=True)
        html = response.data.decode()
        assert 'No results' in html or 'upload' in html.lower()

    def test_save_without_results_redirects(self):
        """Saving without a valid results path should redirect."""
        response = self.client.post('/grading/save', data={
            'results_path': '/nonexistent/path.json',
            'criteria_count': '0'
        }, follow_redirects=True)
        html = response.data.decode()
        assert 'Could not find' in html or 'Upload' in html


class TestNavigation:
    """Tests for general navigation and page structure."""

    def setup_method(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_navbar_present(self):
        """Every page should have the Bootstrap navbar."""
        response = self.client.get('/')
        html = response.data.decode()
        assert 'navbar' in html
        assert 'FYP Grading Tool' in html

    def test_404_handling(self):
        """Non-existent pages should return 404."""
        response = self.client.get('/nonexistent-page')
        assert response.status_code == 404

    def test_static_css_loads(self):
        """The custom CSS file should be accessible."""
        response = self.client.get('/static/css/style.css')
        assert response.status_code == 200