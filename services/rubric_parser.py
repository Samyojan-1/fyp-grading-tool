"""
Rubric Parser Service
--------------------
Parses marking rubrics using AI to extract:
- Criteria names
- Weightings
- Grade band descriptors

The parsed rubric is saved as JSON for reuse (FR-05, FR-37).
"""

import os
import json
from datetime import datetime
from services.ai_grader import call_ai
from services.file_parser import extract_text
import config


# The prompt that tells the AI how to parse the rubric
# This is stored here (not hardcoded in a route) per NFR-09
RUBRIC_PARSE_PROMPT = """You are a marking rubric parser for university Final Year Projects.

Your job is to extract ALL grading criteria from the rubric provided.
You must be thorough and extract EVERY detail — do not skip or summarise anything.

For EACH criterion, extract:
1. The criterion name exactly as it appears in the rubric (the bold heading)
2. The criterion description/guiding question that appears below the name (the regular text that explains what to look for)
3. The weighting/percentage — if not explicitly stated, estimate based on context
4. ALL grade band descriptors — extract EVERY grade band that exists in the rubric

CRITICAL RULES:
- Extract ALL grade bands exactly as they appear in the rubric (e.g. 0-29, 30-39, 40-49, 50-59, 60-69, 70-79, 80-100 or however the rubric defines them)
- Do NOT skip lower grade bands — every band is equally important for fair grading
- Do NOT rename or relabel the grade bands — use the exact labels/ranges from the rubric
- Do NOT summarise the grade band descriptions — extract them in full detail
- The grade bands structure must match what the rubric actually contains
- Different rubrics may have different numbers of grade bands — extract whatever exists
- Weightings must add up to 100 (or close to it)
- Extract ALL criteria, not just a few

Return your response as a JSON object with this EXACT structure:
{
    "rubric_name": "A short descriptive name for this rubric",
    "criteria": [
        {
            "name": "Criterion Name As It Appears In Rubric",
            "description": "The guiding question or description that appears below the criterion name, extracted in full",
            "weighting": 20,
            "grade_bands": [
                {
                    "range": "70-100",
                    "label": "Excellent or whatever label the rubric uses",
                    "description": "Full description from the rubric — do not summarise"
                },
                {
                    "range": "60-69",
                    "label": "Good or whatever label the rubric uses",
                    "description": "Full description from the rubric — do not summarise"
                }
            ]
        }
    ],
    "total_weighting": 100
}

NOTE: The grade_bands array should contain ALL bands from the rubric, ordered from highest to lowest. The example above shows only 2 bands for brevity — your output must include every single band that exists in the rubric.

Return ONLY the JSON object, no other text.
"""


def parse_rubric(rubric_file_path):
    """
    Parse a rubric file and extract criteria using AI.
    
    Steps:
    1. Extract text from the rubric PDF
    2. Send it to the AI with parsing instructions
    3. Return the parsed result
    """
    # Step 1: Extract text from the rubric
    extraction = extract_text(rubric_file_path)
    
    if 'error' in extraction:
        return {'error': f'Could not read rubric: {extraction["error"]}'}
    
    rubric_text = extraction['text']
    
    if not rubric_text.strip():
        return {'error': 'Rubric file appears to be empty or unreadable.'}
    
    # Step 2: Send to AI for parsing (FR-09, FR-38)
    result = call_ai(
        developer_prompt=RUBRIC_PARSE_PROMPT,
        user_prompt=f"Here is the marking rubric to parse:\n\n{rubric_text}",
        expect_json=True
    )
    
    # Step 3: Validate the result
    if isinstance(result, dict) and 'error' in result:
        return result
    
    # Basic validation — make sure we got criteria back
    if 'criteria' not in result or len(result['criteria']) == 0:
        return {'error': 'AI could not extract any criteria from this rubric.'}
    
    # Basic validation — make sure we got criteria back
    if 'criteria' not in result or len(result['criteria']) == 0:
        return {'error': 'AI could not extract any criteria from this rubric.'}
    
    # DEBUG: Print what we parsed so we can verify
    # print("\n" + "="*50)
    # print("DEBUG: Parsed rubric data:")
    # print(f"Rubric name: {result.get('rubric_name')}")
    # print(f"Number of criteria: {len(result['criteria'])}")
    # for i, criterion in enumerate(result['criteria']):
    #     print(f"\nCriterion {i+1}: {criterion['name']} ({criterion['weighting']}%)")
    #     print(f"  Grade bands: {len(criterion.get('grade_bands', []))}")
    #     if criterion.get('grade_bands'):
    #         print(f"  First band keys: {list(criterion['grade_bands'][0].keys())}")
    #     for band in criterion.get('grade_bands', []):
    #         desc_preview = band.get('description', 'NO DESCRIPTION')[:80]
    #         print(f"    {band.get('range')}: {desc_preview}...")
    # print("="*50 + "\n")
    return result


def save_rubric(parsed_rubric, original_filename):
    """
    Save a parsed rubric as a JSON file in the rubrics folder (FR-37).
    
    The filename is human-readable: RubricName_2026-04-03.json
    Returns the saved filename.
    """
    # Make sure the rubrics folder exists
    os.makedirs(config.RUBRIC_FOLDER, exist_ok=True)
    
    # Create a clean filename from the rubric name
    rubric_name = parsed_rubric.get('rubric_name', 'Unknown_Rubric')
    # Replace spaces and special chars with underscores
    clean_name = "".join(c if c.isalnum() else '_' for c in rubric_name)
    date_str = datetime.now().strftime('%Y-%m-%d')
    filename = f"{clean_name}_{date_str}.json"
    
    filepath = os.path.join(config.RUBRIC_FOLDER, filename)
    
    # Save as formatted JSON (indent=2 makes it human-readable)
    with open(filepath, 'w') as f:
        json.dump(parsed_rubric, f, indent=2)
    
    return filename


def load_rubric(filename):
    """Load a previously saved rubric JSON file."""
    filepath = os.path.join(config.RUBRIC_FOLDER, filename)
    
    if not os.path.exists(filepath):
        return {'error': f'Rubric file not found: {filename}'}
    
    with open(filepath, 'r') as f:
        return json.load(f)