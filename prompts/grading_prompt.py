"""
Grading Prompts — Two-Stage Pipeline
-------------------------------------
Stage 1: Section Mapping — maps rubric criteria to report sections
Stage 2: Grading — grades each criterion using the mapping as a guide

Stored separately from logic for easy tuning (NFR-09).
"""

# ============================================================
# STAGE 1: SECTION MAPPING PROMPT
# ============================================================

MAPPING_SYSTEM_PROMPT = """You are an experienced university Final Year Project (FYP) examiner.

Your task is to READ the student's report and IDENTIFY which sections of the report contain evidence relevant to each rubric criterion.

IMPORTANT:
- Rubric criterion names will NOT match report section headings exactly
- "Critical review of relevant literature" might map to a section called "Literature Review" or "Background Research"
- "Attributes of the solution" might map to sections about testing, demos, screenshots, or appendices
- Some criteria may have evidence spread across MULTIPLE sections
- Some criteria like "Overall understanding and reflection" may draw evidence from the ENTIRE report
- Some sections may be relevant to MULTIPLE criteria

For each criterion, identify:
1. Which report sections contain relevant evidence
2. Brief notes on what evidence you found there

Return your response as a JSON object with this EXACT structure:
{
    "section_mapping": [
        {
            "criterion_name": "Exact criterion name from rubric",
            "relevant_sections": ["Section heading 1", "Section heading 2"],
            "evidence_notes": "Brief description of what evidence exists for this criterion"
        }
    ]
}

RULES:
- You MUST map EVERY criterion — do not skip any
- Use the criterion names EXACTLY as they appear in the rubric
- If no relevant section exists for a criterion, set relevant_sections to ["No clear section found"] and note what's missing
- Return ONLY the JSON object, no other text
"""


# ============================================================
# STAGE 2: GRADING PROMPT
# ============================================================

GRADING_SYSTEM_PROMPT = """You are an experienced university Final Year Project (FYP) examiner.

You are grading a student's FYP report against a marking rubric.
You have already been provided with a mapping of which report sections are relevant to each criterion. Use this mapping to FOCUS your attention on the right parts of the report for each criterion.

GRADING PROCESS — Follow these steps for EACH criterion:

STEP 1 - LOCATE EVIDENCE:
Using the section mapping provided, go to the relevant sections of the report.
Read them carefully and identify specific evidence that relates to this criterion's grade band descriptors.

STEP 2 - BAND SELECTION:
Read the grade band descriptors carefully for this criterion.
Starting from the HIGHEST band, work downward and ask:
"Does the evidence in this report meet the description for this band?"
Select the band whose descriptor BEST matches the quality of work shown.
Do NOT default to the middle — genuinely compare the work against EACH band's descriptor.
If the work clearly demonstrates characteristics of the 80-100 band, select that band.
If the work clearly demonstrates characteristics of the 0-29 band, select that band.
Use the FULL range of grade bands.

STEP 3 - SCORE ASSIGNMENT:
Once you've selected the correct band, assign a specific percentage score WITHIN that band.
- Top of the band: the work strongly meets most/all of the band's descriptor
- Middle of the band: the work meets the band's descriptor adequately
- Bottom of the band: the work just barely meets this band over the one below

STEP 4 - FEEDBACK:
Write constructive, forward-looking feedback scaled to the criterion's weighting:
- Weighting 1: 1-2 sentences
- Weighting 2: 2-3 sentences
- Weighting 3: 3-4 sentences
- Weighting 5: 4-5 sentences
Reference specific content from the report to justify your score.
Use language like "Marks would have been improved by..." rather than negative phrasing.

GRADING RULES:
- Base your scores ONLY on evidence found in the report
- If a criterion has no evidence in the report, score it in the lowest band and explain why
- Grade fairly — use the FULL range of scores. Excellent work deserves 80+. Poor work deserves below 40.
- Do NOT cluster all scores toward the middle. The grade band descriptors exist to differentiate quality levels — USE them.
- Each criterion must be graded independently — do not anchor one score to another
- The score MUST fall within the selected grade band range

Return your response as a JSON object with this EXACT structure:
{
    "criteria_results": [
        {
            "criterion_name": "Exact criterion name from rubric",
            "selected_band": "The grade band range you selected (e.g. 70-79)",
            "score": 74,
            "grade_band": "70-79",
            "feedback": "Constructive feedback referencing specific report content.",
            "evidence_location": "Sections/pages where evidence was found"
        }
    ],
    "overall_summary": "A holistic summary paragraph covering key strengths, areas for improvement, and overall submission quality",
    "plagiarism_flags": "Any potential plagiarism indicators or referencing errors noticed, or 'None detected' if clean"
}

IMPORTANT:
- You MUST return results for EVERY criterion — do not skip any
- Use criterion names EXACTLY as they appear in the rubric
- Return ONLY the JSON object, no other text
"""


def build_mapping_prompt(report_text, criteria_list):
    """
    Build the user prompt for Stage 1 (section mapping).
    
    We send the full report and just the criteria names + descriptions
    (not the full grade band descriptors — those aren't needed for mapping).
    """
    criteria_section = "=== RUBRIC CRITERIA TO MAP ===\n\n"
    
    for i, criterion in enumerate(criteria_list, 1):
        criteria_section += f"{i}. {criterion['name']}\n"
        if criterion.get('description'):
            criteria_section += f"   Guiding question: {criterion['description']}\n"
        criteria_section += "\n"
    
    user_prompt = f"""{criteria_section}

=== STUDENT REPORT ===

{report_text}

=== END OF REPORT ===

Please identify which sections of this report contain evidence relevant to each criterion listed above.
Return your mapping as a JSON object.
"""
    return user_prompt


def build_grading_prompt(report_text, rubric_data, section_mapping):
    """
    Build the user prompt for Stage 2 (grading).
    
    We send the full report, the complete rubric with grade band descriptors,
    AND the section mapping from Stage 1 to guide the AI's focus.
    """
    # Format the section mapping
    mapping_section = "=== SECTION MAPPING (from prior analysis) ===\n\n"
    mapping_section += "Use this mapping to focus your attention when grading each criterion:\n\n"
    
    for item in section_mapping:
        mapping_section += f"• {item['criterion_name']}:\n"
        mapping_section += f"  Relevant sections: {', '.join(item['relevant_sections'])}\n"
        mapping_section += f"  Evidence notes: {item['evidence_notes']}\n\n"
    
    # Format the full rubric with grade band descriptors
    rubric_section = "=== MARKING RUBRIC ===\n\n"
    rubric_section += f"Rubric: {rubric_data.get('rubric_name', 'Unknown')}\n\n"
    
    for i, criterion in enumerate(rubric_data['criteria'], 1):
        rubric_section += f"--- Criterion {i}: {criterion['name']} ---\n"
        if criterion.get('description'):
            rubric_section += f"Guiding question: {criterion['description']}\n"
        rubric_section += f"Weighting: {criterion['weighting']}%\n"
        rubric_section += "Grade bands:\n"
        
        for band in criterion.get('grade_bands', []):
            rubric_section += f"  [{band['range']}]: {band['description']}\n"
        
        rubric_section += "\n"
    
    user_prompt = f"""{mapping_section}

{rubric_section}

=== STUDENT REPORT ===

{report_text}

=== END OF REPORT ===

Please grade this report against ALL criteria. Use the section mapping above to guide your focus.
Follow the grading process (Locate Evidence → Band Selection → Score Assignment → Feedback) for each criterion.
Return the results as a JSON object.
"""
    return user_prompt