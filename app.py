from flask import Flask
from routes.upload import upload_bp

# Create the Flask app
app = Flask(__name__)

# Register the upload blueprint
# This "plugs in" all the routes defined in routes/upload.py
app.register_blueprint(upload_bp)

if __name__ == '__main__':
    app.run(debug=True, port=5001)