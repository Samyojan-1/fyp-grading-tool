# test_api.py
import time
from dotenv import load_dotenv
load_dotenv()

from services.rubric_parser import parse_rubric

rubric_path = "/Users/samyojandevkota/Desktop/SUMS_Marking_Criteria.pdf"

print("Starting rubric parse on CURRENT branch...")
start = time.time()

result = parse_rubric(rubric_path)

elapsed = time.time() - start
print(f"Completed in {elapsed:.1f}s")

if isinstance(result, dict) and 'error' in result:
    print(f"Error: {result['error']}")
else:
    print(f"Success! Found {len(result.get('criteria', []))} criteria")
