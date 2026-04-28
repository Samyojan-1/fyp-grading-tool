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
import time
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
    
    Includes automatic retry with exponential backoff for rate limit
    and timeout errors. Retries up to 3 times with doubling wait times
    (2s, 4s, 8s) before giving up.
    """    
    max_retries = 3
    base_wait = 2  # Starting wait time in seconds
    
    for attempt in range(max_retries + 1):  # 0, 1, 2, 3 — first attempt + 3 retries
        try:
            client = get_client()
            
            messages = [
                {"role": "developer", "content": developer_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = client.chat.completions.create(
                model=config.AZURE_DEPLOYMENT,
                messages=messages,
                max_completion_tokens=16000,
                reasoning_effort=reasoning_effort
            )
            
            # Debug output
            print(f"\n{'='*50}")
            print(f"DEBUG: API response (attempt {attempt + 1})")
            print(f"Finish reason: {response.choices[0].finish_reason}")
            print(f"Usage: {response.usage}")
            print(f"{'='*50}\n")
            
            result_text = response.choices[0].message.content
            
            if not result_text:
                return {
                    'error': f'AI returned empty response. Finish reason: {response.choices[0].finish_reason}.'
                }
            
            if expect_json:
                import re
                cleaned = result_text.strip()
                if cleaned.startswith('```json'):
                    cleaned = cleaned[7:]
                if cleaned.startswith('```'):
                    cleaned = cleaned[3:]
                if cleaned.endswith('```'):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
                
                cleaned = re.sub(r'\n', ' ', cleaned)
                cleaned = re.sub(r' +', ' ', cleaned)
                
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    print(f"\nDEBUG: JSON parsing failed")
                    print(f"First 100 chars: {repr(cleaned[:100])}")
                    return {
                        'error': 'AI response was not valid JSON',
                        'raw_response': result_text
                    }
            
            return result_text
        
        except Exception as e:
            error_msg = str(e)
            
            # Check if this is a retryable error
            is_rate_limit = '429' in error_msg
            is_timeout = 'timeout' in error_msg.lower()
            is_server_error = '500' in error_msg or '502' in error_msg or '503' in error_msg
            
            is_retryable = is_rate_limit or is_timeout or is_server_error
            
            if is_retryable and attempt < max_retries:
                # Calculate wait time: 2, 4, 8 seconds
                wait_time = base_wait * (2 ** attempt)
                print(f"\n⚠️  API error (attempt {attempt + 1}/{max_retries + 1}): {error_msg}")
                print(f"   Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue  # Go to next attempt
            
            # Either not retryable or we've exhausted retries
            if is_rate_limit:
                return {'error': f'Rate limit exceeded after {attempt + 1} attempts. Please wait a moment and try again.'}
            elif is_timeout:
                return {'error': f'Request timed out after {attempt + 1} attempts. The report may be too long.'}
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

        