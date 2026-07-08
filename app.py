from flask import Flask
from dotenv import load_dotenv
from routes.upload import upload_bp
from routes.grading import grading_bp
from routes.batch import batch_bp
import config

# Loading environment variables from .env file
load_dotenv()

# Creating the Flask app
app = Flask(__name__)

# For future use, to sign session cookies, to be changed before deploying
app.config['SECRET_KEY'] = 'dev-secret-key-change-later'
app.config['MAX_CONTENT_LENGTH'] = config.MAX_FILE_SIZE_MB * 1024 * 1024  # Converting MB to bytes

# Registering blueprints
app.register_blueprint(upload_bp)
app.register_blueprint(grading_bp)
app.register_blueprint(batch_bp)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
    