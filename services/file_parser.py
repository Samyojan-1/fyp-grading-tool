# Extracts text from DOCX and PDF files. 

import fitz  # This is PyMuPDF 
import pymupdf4llm
# from docx import Document

def extract_text_from_pdf(file_path):
    """
    Extract text from a PDF file using PyMuPDF4LLM.
    """
    try:
        # import pymupdf4llm
        # import fitz  

        # Fast pre-check for scanned PDFs using plain fitz 
        doc = fitz.open(file_path)
        page_count = len(doc)
        quick_text = "".join(page.get_text() for page in doc)
        doc.close()

        avg_chars_per_page = len(quick_text.strip()) / max(page_count, 1)
        if avg_chars_per_page < 50:
            return {
                'text': '',
                'pages': [],
                'page_count': page_count,
                'is_scanned': True
            }

        # PDF has extractable text
        # page_chunks=True gives us the text broken down by page
        md_pages = pymupdf4llm.to_markdown(file_path, page_chunks=True)

        pages = []
        full_text = ""

        for i, page_data in enumerate(md_pages):
            page_text = page_data['text']
            pages.append({
                'page_number': i + 1,
                'text': page_text
            })
            full_text += page_text + "\n"

        return {
            'text': full_text.strip(),
            'pages': pages,
            'page_count': len(pages),
            'is_scanned': False
        }
    
    except Exception as e:
        return {
            'text': '',
            'pages': [],
            'page_count': 0,
            'is_scanned': False,
            'error': f'Failed to parse PDF: {str(e)}'
        }

def extract_text_from_docx(file_path):
    """
    Extract text from a DOCX and convert to Markdown using Pandoc.
    We call Pandoc as a subprocess from Python.
    """
    try:
        import subprocess
        
        # subprocess.run() is used to run a terminal command from Python
        result = subprocess.run(
            ['pandoc', file_path, '-t', 'markdown'],
            capture_output=True,
            text=True,
            check=True
        )
        
        full_text = result.stdout.strip()
        
        # Split into paragraphs for consistency with our data structure
        # Double newlines separate paragraphs in Markdown
        raw_paragraphs = full_text.split('\n\n')
        paragraphs = []
        for para in raw_paragraphs:
            if para.strip():
                # Detect the style from Markdown syntax
                stripped = para.strip()
                if stripped.startswith('# '):
                    style = 'Heading 1'
                elif stripped.startswith('## '):
                    style = 'Heading 2'
                elif stripped.startswith('### '):
                    style = 'Heading 3'
                elif stripped.startswith('- ') or stripped.startswith('* '):
                    style = 'List'
                else:
                    style = 'Normal'
                
                paragraphs.append({
                    'text': stripped,
                    'style': style
                })
        
        return {
            'text': full_text,
            'paragraphs': paragraphs,
            'paragraph_count': len(paragraphs),
            'is_scanned': False
        }
    
    except FileNotFoundError:
        # This means pandoc isn't installed
        return {
            'text': '',
            'paragraphs': [],
            'paragraph_count': 0,
            'is_scanned': False,
            'error': 'Pandoc is not installed. Install it with: brew install pandoc'
        }
    except subprocess.CalledProcessError as e:
        # Pandoc ran but failed (e.g. corrupt DOCX)
        return {
            'text': '',
            'paragraphs': [],
            'paragraph_count': 0,
            'is_scanned': False,
            'error': f'Failed to parse DOCX: {e.stderr}'
        }
    except Exception as e:
        return {
            'text': '',
            'paragraphs': [],
            'paragraph_count': 0,
            'is_scanned': False,
            'error': f'Failed to parse DOCX: {str(e)}'
        }
    
# def extract_text_from_docx(file_path):
#     """
#     Extract text from a DOCX file using python-docx.
    
#     DOCX files don't have "pages" in the same way PDFs do —
#     page breaks depend on the printer/viewer settings.
#     So we extract paragraphs instead, which maps better to
#     document structure (headings, sections, etc.)
#     """
#     try:
#         # Document() loads the DOCX file
#         doc = Document(file_path)
        
#         paragraphs = []
#         full_text = ""
        
#         for para in doc.paragraphs:
#             # Skip empty paragraphs
#             if para.text.strip():
#                 paragraphs.append({
#                     'text': para.text.strip(),
#                     # para.style.name tells us if it's a heading, normal text, etc.
#                     # This will be useful later for section detection (FR-36)
#                     'style': para.style.name
#                 })
#                 full_text += para.text.strip() + "\n"
        
#         return {
#             'text': full_text.strip(),
#             'paragraphs': paragraphs,
#             'paragraph_count': len(paragraphs),
#             'is_scanned': False  # DOCX files are always text-based
#         }
    
#     except Exception as e:
#         return {
#             'text': '',
#             'paragraphs': [],
#             'paragraph_count': 0,
#             'is_scanned': False,
#             'error': f'Failed to parse DOCX: {str(e)}'
#         }


def extract_text(file_path):
    """
    Main entry point. 
    Detects file type and calls the right extractor.
    This is the function other parts of the app will call.
    """
    if file_path.lower().endswith('.pdf'):
        return extract_text_from_pdf(file_path)
    elif file_path.lower().endswith('.docx'):
        return extract_text_from_docx(file_path)
    else:
        return {
            'text': '',
            'error': f'Unsupported file type: {file_path}'
        }
    
