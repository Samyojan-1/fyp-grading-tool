"""
File Parser Service
-------------------
Responsible for extracting text from PDF and DOCX files.
This module knows NOTHING about Flask, routes, or web requests.
It just takes a file path and returns text. That's it.
"""

import fitz  # This is PyMuPDF — confusing, but that's the import name
import pymupdf4llm
# from docx import Document

def extract_text_from_pdf(file_path):
    """
    Extract text from a PDF file using PyMuPDF4LLM.
    
    Why pymupdf4llm instead of plain PyMuPDF?
    - Outputs Markdown, which preserves document structure (headings, tables, lists)
    - LLMs understand Markdown natively, so the AI gets better context
    - Section headers become # headers, making FR-36 (section detection) easier
    """
    try:
        import pymupdf4llm
        import fitz  # Still need this for page count and scanned PDF detection

        # Fast pre-check for scanned PDFs using plain fitz (FR-04)
        # pymupdf4llm.to_markdown is very slow on scanned PDFs because it processes
        # page images — this check avoids that by using fitz.get_text() which is instant.
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

        # PDF has extractable text — proceed with pymupdf4llm for rich Markdown output
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
    Extract text from a DOCX file and convert to Markdown using Pandoc.
    
    Why Pandoc?
    - It's the gold standard for document format conversion
    - Produces high-quality Markdown from DOCX (headings, bold, italic, tables, lists)
    - Output quality is comparable to pymupdf4llm for PDFs
    - This ensures consistent AI input regardless of file format
    
    We call Pandoc as a subprocess (command-line tool) from Python.
    subprocess.run() is Python's way of running terminal commands programmatically.
    """
    try:
        import subprocess
        
        # subprocess.run() executes a terminal command from Python
        # It's like typing this in Terminal: pandoc input.docx -t markdown
        # 
        # capture_output=True — captures what the command prints (stdout)
        # text=True — returns the output as a string, not bytes
        # check=True — raises an error if the command fails
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
    Main entry point — detects file type and calls the right extractor.
    
    This is the function other parts of the app will call.
    They don't need to know whether it's a PDF or DOCX —
    they just call extract_text() and get back the result.
    
    This pattern is called a "facade" — a simple interface
    that hides the complexity behind it.
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
    
