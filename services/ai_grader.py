"""
AI Grader Service
-----------------
Handles all communication with Azure OpenAI (GPT-5 series).

IMPORTANT: GPT-5 models use a different API pattern than older models:
- Uses OpenAI client (not AzureOpenAI)
- Uses base_url pointing to /openai/v1/
- Uses "developer" role instead of "system" role
- Uses max_completion_tokens instead of max_tokens
- Does NOT support temperature, top_p, or other sampling parameters
- Supports reasoning_effort (low/medium/high) to control thinking depth

Reference: https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reasoning
"""

import os
import json
from openai import OpenAI
import config


def get_client():
    """
    Create and return an OpenAI client configured for Azure.
    
    GPT-5 models on Azure use the OpenAI client (not AzureOpenAI)
    with a base_url pointing to the Azure endpoint.
    This is different from older models like GPT-4o — it's the new pattern.
    """
    client = OpenAI(
        api_key=config.AZURE_API_KEY,
        base_url=config.AZURE_ENDPOINT  # e.g. https://your-resource.openai.azure.com/openai/v1/
    )
    return client


def call_ai(developer_prompt, user_prompt, expect_json=True, reasoning_effort="medium"):
    """
    Send a prompt to Azure OpenAI GPT-5-mini and get a response.
    
    Parameters:
    - developer_prompt: instructions for the AI (replaces "system" role in older models)
    - user_prompt: the actual question or data to process
    - expect_json: if True, we try to parse the response as JSON (FR-38)
    - reasoning_effort: "low", "medium", or "high" — controls how much the model
                        "thinks" before answering. Higher = more accurate but slower/costlier.
                        For rubric parsing we use "medium", for grading maybe "high".
    
    Returns:
    - The AI's response as a string (or parsed JSON dict if expect_json=True)
    - Or a dict with 'error' key if something went wrong
    """
    try:
        client = get_client()
        
        messages = [
            {"role": "developer", "content": developer_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = client.chat.completions.create(
            model=config.AZURE_DEPLOYMENT,
            messages=messages,
            max_completion_tokens=20000,  # Increased — reasoning tokens are hidden and count toward this
            reasoning_effort=reasoning_effort
        )
        
        # DEBUG: Print the full response details so we can see what's happening
        # print("\n" + "="*50)
        # print("DEBUG: Full API response details:")
        # print(f"Finish reason: {response.choices[0].finish_reason}")
        # print(f"Usage: {response.usage}")
        # if hasattr(response.choices[0].message, 'refusal') and response.choices[0].message.refusal:
        #     print(f"REFUSAL: {response.choices[0].message.refusal}")
        # print("="*50 + "\n")
        
        result_text = response.choices[0].message.content
        
        # Check if content is None or empty
        if not result_text:
            return {
                'error': f'AI returned empty response. Finish reason: {response.choices[0].finish_reason}. '
                         f'This may be due to content filtering or token limits.'
            }
        
        # If we expect JSON, try to parse it
        if expect_json:
            cleaned = result_text.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            try:
                # GPT-5 sometimes returns JSON with raw newlines inside string values
                # (inherited from PDF text extraction line breaks)
                # These break json.loads(), so we need to escape them properly
                # We replace actual newline characters inside strings with spaces
                # This is safe because JSON structure newlines are between keys/values,
                # not inside quoted strings
                import re
                # Replacing newlines that appear inside string values with spaces
                # This regex finds content between quotes and replaces \n with space
                cleaned = re.sub(r'\n', ' ', cleaned)
                # Cleaning up any double/triple spaces that resulted
                cleaned = re.sub(r' +', ' ', cleaned)
                return json.loads(cleaned)
            except json.JSONDecodeError:
                # print("\n" + "="*50)
                # print("DEBUG: AI response that failed JSON parsing:")
                # print("="*50)
                # print(result_text)
                # print("="*50)
                # print(f"First 50 chars: {repr(result_text[:50])}")
                # print(f"Last 50 chars: {repr(result_text[-50:])}")
                # print("="*50 + "\n")
                return {
                    'error': 'AI response was not valid JSON',
                    'raw_response': result_text
                }
        
        return result_text
    
    except Exception as e:
        error_msg = str(e)
        
        if '429' in error_msg:
            return {'error': 'Rate limit exceeded. Please wait a moment and try again.'}
        elif 'timeout' in error_msg.lower():
            return {'error': 'Request timed out. The report may be too long. Please try again.'}
        elif '401' in error_msg or 'auth' in error_msg.lower():
            return {'error': 'Authentication failed. Check your Azure API key in .env file.'}
        else:
            return {'error': f'AI service error: {error_msg}'}
        
def map_sections(report_text, rubric_data):
    """
    Stage 1: Map report sections to rubric criteria.
    
    Sends the full report + criteria names to the AI.
    Returns a mapping of which sections are relevant to each criterion.
    """
    from prompts.grading_prompt import MAPPING_SYSTEM_PROMPT, build_mapping_prompt
    
    user_prompt = build_mapping_prompt(report_text, rubric_data['criteria'])
    
    estimated_tokens = len(user_prompt) // 4
    print(f"\n{'='*50}")
    print(f"STAGE 1 - MAPPING: Sending ~{estimated_tokens} estimated tokens")
    print(f"{'='*50}\n")
    
    result = call_ai(
        developer_prompt=MAPPING_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        expect_json=True,
        reasoning_effort="medium"  # Mapping is simpler than grading
    )
    
    if isinstance(result, dict) and 'error' in result:
        return result
    
    if 'section_mapping' not in result:
        return {'error': 'AI response missing section_mapping'}
    
    print(f"\n{'='*50}")
    print("STAGE 1 COMPLETE - Section mapping:")
    for item in result['section_mapping']:
        print(f"  {item['criterion_name']}")
        print(f"    → {', '.join(item['relevant_sections'])}")
    print(f"{'='*50}\n")
    
    return result


def grade_report(report_text, rubric_data):
    """
    Two-stage grading pipeline.
    
    Stage 1: Map report sections to criteria (one API call)
    Stage 2: Grade all criteria using the mapping (one API call)
    
    This decomposition is supported by research showing that
    separating evidence identification from scoring improves
    accuracy and reduces central tendency bias.
    """
    from prompts.grading_prompt import GRADING_SYSTEM_PROMPT, build_grading_prompt
    
    # === STAGE 1: Section Mapping ===
    mapping_result = map_sections(report_text, rubric_data)
    
    if 'error' in mapping_result:
        return {'error': f'Stage 1 (mapping) failed: {mapping_result["error"]}'}
    
    section_mapping = mapping_result['section_mapping']
    
    # === STAGE 2: Grading ===
    user_prompt = build_grading_prompt(report_text, rubric_data, section_mapping)
    
    estimated_tokens = len(user_prompt) // 4
    print(f"\n{'='*50}")
    print(f"STAGE 2 - GRADING: Sending ~{estimated_tokens} estimated tokens")
    print(f"{'='*50}\n")
    
    result = call_ai(
        developer_prompt=GRADING_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        expect_json=True,
        reasoning_effort="medium"  # High effort for grading accuracy
    )
    
    if isinstance(result, dict) and 'error' in result:
        return {'error': f'Stage 2 (grading) failed: {result["error"]}'}
    
    if 'criteria_results' not in result:
        return {'error': 'AI response missing criteria_results'}
    
    # Store the mapping in the result for traceability (FR-13)
    result['section_mapping'] = section_mapping
    
    # Calculate overall weighted score (FR-19)
    result = calculate_overall_score(result, rubric_data)
    
    return result


def calculate_overall_score(grading_result, rubric_data):
    """
    Calculate the overall weighted score from individual criterion scores (FR-19).
    Uses word-overlap similarity for matching criterion names.
    """
    total_weighted_score = 0
    total_weight = 0
    
    rubric_criteria = rubric_data['criteria']
    
    for criteria_result in grading_result['criteria_results']:
        criterion_name = criteria_result['criterion_name'].lower().strip()
        
        best_match = None
        best_score = 0
        
        for rubric_criterion in rubric_criteria:
            rubric_name = rubric_criterion['name'].lower().strip()
            
            criterion_words = set(criterion_name.split())
            rubric_words = set(rubric_name.split())
            common_words = criterion_words & rubric_words
            
            if len(criterion_words) == 0 or len(rubric_words) == 0:
                continue
            
            similarity = len(common_words) / max(len(criterion_words), len(rubric_words))
            
            if similarity > best_score:
                best_score = similarity
                best_match = rubric_criterion
        
        if best_match and best_score > 0.3:
            matching_weight = best_match['weighting']
        else:
            matching_weight = 100 / len(grading_result['criteria_results'])
            print(f"WARNING: Poor match for '{criteria_result['criterion_name']}' "
                  f"(best similarity: {best_score:.2f}). Using default weight.")
        
        score = criteria_result.get('score', 0)
        total_weighted_score += score * matching_weight
        total_weight += matching_weight
        criteria_result['weighting'] = round(matching_weight, 2)
    
    if total_weight > 0:
        overall_score = round(total_weighted_score / total_weight, 1)
    else:
        overall_score = 0
    
    # Determine grade band from rubric's actual bands
    grade_bands = rubric_data['criteria'][0].get('grade_bands', [])
    overall_band = "Unknown"
    for band in grade_bands:
        band_range = band['range'].replace('–', '-')
        parts = band_range.split('-')
        if len(parts) == 2:
            try:
                low = int(parts[0].strip())
                high = int(parts[1].strip())
                if low <= overall_score <= high:
                    overall_band = band['range']
                    break
            except ValueError:
                continue
    
    grading_result['overall_score'] = overall_score
    grading_result['overall_grade_band'] = overall_band
    
    return grading_result

        