import os

# Loading the API key from the .env file
AZURE_API_KEY = os.getenv('AZURE_OPENAI_KEY')
AZURE_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_DEPLOYMENT = os.getenv('AZURE_OPENAI_DEPLOYMENT')

# File upload settings (FR-03: max 250MB)
MAX_FILE_SIZE_MB = 250
ALLOWED_REPORT_EXTENSIONS = {'pdf', 'docx'}
ALLOWED_RUBRIC_EXTENSIONS = {'pdf'}

# Bulk grading: how many reports to grade at the same time.
# The limit is Azure OpenAI's rate limits, not Flask — keep this small (2-3).
MAX_PARALLEL_REPORTS = 2

# Folder paths: using os.path so it works on any operating system
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
RUBRIC_FOLDER = os.path.join(BASE_DIR, 'rubrics')


