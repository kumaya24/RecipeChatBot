from langchain.tools import tool
from elasticsearch import Elasticsearch
import json
import argparse

# Connect to the Docker instance
es = Elasticsearch(
    "http://localhost:9200",
    verify_certs=False,
    request_timeout=30
)



@tool
def search_recipes(query_text: str, max_calories: int = None):
    """
    Search the local recipe database for recipe ideas, ingredients, and instructions.
    
    Args:
        query_text: The main subject of the search. Can be an ingredient (e.g., 'banana'), 
                   a dish type (e.g., 'muffins'), or a general query.
        max_calories: (Optional) The upper limit of calories per serving. 
                      Only provide this if the user mentions a diet, health goal, 
                      or a specific calorie number.
    
    Use this tool only when the user is looking for new recipes or doesn't know 
    what to cook. If the user is asking about a recipe already found in the chat 
    history, do NOT use this tool; answer from memory instead.
    """
    search_query = {
        "bool": {
            "must": [
                {
                    "multi_match": {
                        "query": query_text,
                        "fields": ["title^2", "ingredients", "steps"],
                        "fuzziness": "AUTO"
                    }
                }
            ]
        }
    }
    if max_calories:
        search_query["bool"]["filter"] = [
            {"range": {"nutrition.calories": {"lte": max_calories}}}
        ]

    res = es.search(index="recipes", query=search_query, size=3)
    results = [hit["_source"] for hit in res["hits"]["hits"]]
        
    if not results:
        return "No recipes found matching those criteria."
        
    return json.dumps(results)

    #print(f"\nFound {res['hits']['total']['value']} recipes matching '{query_text}':")
    #for hit in res['hits']['hits']:
    #    title = hit['_source'].get('title')
    #    url = hit['_source'].get('source_url')
    #    calories = hit['_source'].get('nutrition', {}).get('calories', 'N/A')
    #    print(f" * {title} ({calories}) {url}")



def main():
    parser = argparse.ArgumentParser(description="Search for recipes in Elasticsearch")
    parser.add_argument("query", help="The ingredient or title to search for")
    parser.add_argument("--cal", type=int, help="Maximum calories allowed")
    
    args = parser.parse_args()

    if es.ping():
        print(search_recipes.invoke({"query_text": args.query, "max_calories": args.cal}))
    else:
        print("Error: Could not connect to Elasticsearch. Is Docker running?")

if __name__ == '__main__':
    main()