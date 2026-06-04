import asyncio
import json
import os

from main import create_plan, ArchitectRequest

async def main():
    # Make sure we have a GOOGLE_API_KEY from environment or tell the user to set it
    if not os.getenv("GOOGLE_API_KEY"):
        print("WARNING: GOOGLE_API_KEY environment variable is not set. The LLM call may fail.")
    
    request = ArchitectRequest(
        career_goal="Data Analyst",
        current_skills="Basic math and spreadsheet usage"
    )
    
    print("Running integration test for Academic Architect agent...")
    try:
        response = await create_plan(request)
        print("\n--- RESPONSE STATUS ---")
        print(response.status)
        print("\n--- GENERATED ROADMAP ---")
        print(response.academic_plan)
    except Exception as e:
        print(f"Error executing plan: {e}")

if __name__ == "__main__":
    asyncio.run(main())
