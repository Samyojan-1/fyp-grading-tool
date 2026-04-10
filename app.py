from flask import Flask
from dotenv import load_dotenv
from routes.upload import upload_bp
from routes.grading import grading_bp
import config

# Load environment variables from .env file
# This MUST happen before anything tries to read os.getenv()
load_dotenv()

# Create the Flask app
app = Flask(__name__)

# Configure the app with our settings
# SECRET_KEY is used by Flask to sign session cookies — it's a security thing
# For now we use a simple key; in production you'd use something random and long
app.config['SECRET_KEY'] = 'dev-secret-key-change-later'
app.config['MAX_CONTENT_LENGTH'] = config.MAX_FILE_SIZE_MB * 1024 * 1024  # Convert MB to bytes

# Register blueprints
app.register_blueprint(upload_bp)
app.register_blueprint(grading_bp)

if __name__ == '__main__':
    app.run(debug=True, port=5001)
    