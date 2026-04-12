import os

# Load the API key from the .env file
# os.getenv() reads environment variables — it returns None if the key doesn't exist
AZURE_API_KEY = os.getenv('AZURE_OPENAI_KEY')
AZURE_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_DEPLOYMENT = os.getenv('AZURE_OPENAI_DEPLOYMENT')

# File upload settings (FR-03: max 250MB)
MAX_FILE_SIZE_MB = 250
ALLOWED_REPORT_EXTENSIONS = {'pdf', 'docx'}
ALLOWED_RUBRIC_EXTENSIONS = {'pdf'}

# Folder paths — using os.path so it works on any operating system
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
RUBRIC_FOLDER = os.path.join(BASE_DIR, 'rubrics')


