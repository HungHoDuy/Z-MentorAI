import asyncio
import json

from course_search_tool import CourseSearchTool

async def test_search():
    searcher = CourseSearchTool()
    # Test with Cloud Engineering (user's preferred test skill)
    skill = "Economic and finance decision making"
    
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
        
    print("\n--- edX Results ---")
    for r in results["edx"]:
        print(f"- {r['title']}")
        print(f"  URL: {r['url']}")
        print(f"  Creator: {r['partner_creator']}")
        print(f"  Rating: {r['rating']}")
        print(f"  Duration/Details: {r['duration_details']}")
        
    print("\n--- YouTube Results ---")
    for r in results["youtube"]:
        print(f"- {r['title']}")
        print(f"  URL: {r['url']}")
        print(f"  Creator: {r['partner_creator']}")
        print(f"  Details: {r['duration_details']}")

if __name__ == "__main__":
    asyncio.run(test_search())
