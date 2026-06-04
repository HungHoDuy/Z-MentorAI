import asyncio
import json

from course_search_tool import CourseSearchTool

async def test_search():
    searcher = CourseSearchTool()
    # Test with a business skill to verify metadata retrieval
    skill = "Negotiation"
    
    print(f"\n==================================================")
    print(f"Selenium Edge Search for: '{skill}'")
    print(f"==================================================")
    results = await searcher.search_all(skill)
    
    print("\n--- Coursera Results ---")
    for r in results["coursera"]:
        print(f"- {r['title']}")
        print(f"  URL: {r['url']}")
        print(f"  Creator: {r['partner_creator']}")
        print(f"  Rating: {r['rating']}")
        print(f"  Duration/Difficulty: {r['duration_details']}")
        
    print("\n--- YouTube Results ---")
    for r in results["youtube"]:
        print(f"- {r['title']}")
        print(f"  URL: {r['url']}")
        print(f"  Creator: {r['partner_creator']}")
        print(f"  Details: {r['duration_details']}")

if __name__ == "__main__":
    asyncio.run(test_search())
