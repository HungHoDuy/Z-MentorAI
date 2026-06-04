import asyncio
import json

from course_search_tool import CourseSearchTool

async def test_search():
    searcher = CourseSearchTool()
    # Test with business and management skills
    skills_to_test = ["Negotiation", "Project Management", "Financial Accounting"]
    
    for skill in skills_to_test:
        print(f"\n==================================================")
        print(f"Searching for: '{skill}'")
        print(f"==================================================")
        results = await searcher.search_all(skill)
        
        print("\n--- Coursera Results ---")
        for r in results["coursera"][:3]:
            print(f"- {r['title']}: {r['url']}")
            
        print("\n--- Udemy Results ---")
        for r in results["udemy"][:3]:
            print(f"- {r['title']}: {r['url']}")
            
        print("\n--- YouTube Results ---")
        for r in results["youtube"][:3]:
            print(f"- {r['title']}: {r['url']}")

if __name__ == "__main__":
    asyncio.run(test_search())
