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
            max_completion_tokens=40000,  # Increased — reasoning tokens are hidden and count toward this
            reasoning_effort=reasoning_effort
        )
        
        # DEBUG: Print the full response details so we can see what's happening
        print("\n" + "="*50)
        print("DEBUG: Full API response details:")
        print(f"Finish reason: {response.choices[0].finish_reason}")
        print(f"Usage: {response.usage}")
        if hasattr(response.choices[0].message, 'refusal') and response.choices[0].message.refusal:
            print(f"REFUSAL: {response.choices[0].message.refusal}")
        print("="*50 + "\n")
        
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
                # Replace newlines that appear inside string values with spaces
                # This regex finds content between quotes and replaces \n with space
                cleaned = re.sub(r'\n', ' ', cleaned)
                # Clean up any double/triple spaces that resulted
                cleaned = re.sub(r' +', ' ', cleaned)
                return json.loads(cleaned)
            except json.JSONDecodeError:
                print("\n" + "="*50)
                print("DEBUG: AI response that failed JSON parsing:")
                print("="*50)
                print(result_text)
                print("="*50)
                print(f"First 50 chars: {repr(result_text[:50])}")
                print(f"Last 50 chars: {repr(result_text[-50:])}")
                print("="*50 + "\n")
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
        