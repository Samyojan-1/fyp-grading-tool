# FYP Grading Tool

A web-based tool that uses AI to automatically grade university Final Year Project (FYP) reports against a marking rubric. Built as a BSc Final Year Project at the University of Portsmouth, 2026.

The tool parses a marking rubric uploaded as a PDF, maps rubric criteria to the relevant sections of a student's report, and grades each criterion against the rubric's grade band descriptors. Results are editable by the marker and can be exported as PDF or Excel.

---

## Tech Stack

- **Backend:** Python, Flask
- **AI:** Azure OpenAI (GPT-5-mini)
- **PDF parsing:** pymupdf4llm
- **DOCX parsing:** Pandoc (system-level)
- **Export:** ReportLab (PDF), openpyxl (Excel)
- **Frontend:** Jinja2 templates, Bootstrap 5

---

## Prerequisites

- Python 3.10+
- [Pandoc](https://pandoc.org/) (required for DOCX report parsing)
- An Azure OpenAI resource with GPT-5 series deployment (e.g. GPT-5-mini)

### Installing pandoc

**macOS (Homebrew):**

```bash
brew install pandoc
```

**Windows:**

Download the installer from https://pandoc.org/installing.html

**Linux (Ubuntu/Debian):**

```bash
sudo apt install pandoc
```

## Azure OpenAI Setup

The tool requires access to Azure OpenAI with a GPT-5 series deployment. To set this up:

1. Go to the Azure Portal (https://portal.azure.com)
2. Create an Azure OpenAI resource (or use an existing one)
3. Go to Azure AI Foundry (https://ai.azure.com)
4. Deploy a GPT-5 series model and note the deployment name
5. From your Azure OpenAI resource, copy your API key and endpoint URL

The endpoint URL should look like:

```
https://your-resource-name.openai.azure.com/openai/v1/
```

Note the `/openai/v1/` suffix, this is required because GPT-5-mini uses the standard OpenAI client rather than the AzureOpenAI client.

---

## Setup

**1. Clone the repository**

```bash
git clone <repo-url>
cd fyp-grading-tool
```

**2. Create and activate a virtual environment**

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Configure environment variables**

Create a `.env` file in the project root:

```
AZURE_OPENAI_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=your_endpoint_here
AZURE_OPENAI_DEPLOYMENT=your_deployment_name_here
```

---

## Running the App

```bash
python app.py
```

The app runs at `http://127.0.0.1:5001`

> Port 5001 is used because macOS AirPlay Receiver occupies the default Flask port 5000.

---

## How to Use

**1. Upload a submission**
- Enter the student's name and student number (format: UP followed by 7 digits, e.g. UP1234567)
- Upload the student's report (PDF or DOCX)
- Either upload a new rubric (PDF) or select a previously saved one from the dropdown

**2. Verify the rubric (new rubric only)**
- The AI parses the rubric and displays the extracted criteria, weightings, and grade band descriptors
- Review the table to confirm the rubric was parsed correctly
- Click "Confirm & save rubric" to proceed (the rubric is saved as JSON for future use)
- Click "Reject & re-upload" to go back and try again

**3. Review grading results**
- The AI grades the report against each criterion (this takes 2–4 minutes)
- Results show a score, grade band, confidence level, and feedback for each criterion
- All scores and feedback are editable (click any field to modify it)
- The overall score updates automatically when scores are changed

**4. Save and export**
- Click "Save final result" to save any edits
- Click "Export as PDF & Excel" to download both formats to the submission folder

---

## Project Structure

```
fyp-grading-tool/
├── app.py                  # App entry point; creates Flask app, registers blueprints
├── config.py               # Configuration; API keys, file paths, allowed extensions
├── requirements.txt        # Python dependencies
├── .env                    # API credentials (not committed to git)
│
├── routes/
│   ├── upload.py           # Upload, rubric parsing, and grading flow
│   └── grading.py          # Results display, save, and export routes
│
├── services/
│   ├── ai_grader.py        # Azure OpenAI client, grading pipeline, score calculation
│   ├── rubric_parser.py    # Rubric PDF parsing using AI
│   ├── file_parser.py      # PDF and DOCX text extraction
│   └── export.py           # PDF and Excel export generation
│
├── prompts/
│   └── grading_prompt.py   # Two-stage grading prompts (section mapping + grading)
│
├── templates/              # Jinja2 HTML templates
│   ├── base.html           # Base layout (navbar, footer, Bootstrap)
│   ├── upload.html         # Upload form
│   ├── rubric_verify.html  # Rubric verification page
│   └── results.html        # Grading results and editing
│
├── static/
│   └── css/style.css       # Custom styles
│
├── rubrics/                # Saved rubric JSON files
├── uploads/                # Submission folders (one per student)
└── tests/                  # Automated test suite
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

---

## Key Technical Notes

- Scanned PDFs (image-based, no extractable text) are not supported (the tool detects these and flags an error message)
- Rubrics must be uploaded as PDF files
- The AI grading pipeline makes two API calls per submission and typically takes 2–4 minutes
- GPT-5-mini uses `max_completion_tokens` instead of `max_tokens`, and `reasoning_effort` instead of `temperature` (temperature is unsupported for reasoning models)
- The tool is designed as an AI-assisted grading aid, not a fully autonomous grader, so markers are expected to review and edit all AI-generated scores and feedback
