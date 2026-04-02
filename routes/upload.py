from flask import Blueprint, render_template

# A Blueprint is like a mini Flask app
# It lets you define routes in separate files and then "plug them in" to the main app
# Think of it as a chapter in a book — each Blueprint is one chapter,
# and app.py is the table of contents that brings them together
upload_bp = Blueprint('upload', __name__)

@upload_bp.route('/')
def upload_page():
    """Show the upload page — this is the homepage of the app."""
    return render_template('upload.html')