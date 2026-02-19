import json
import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from search import search_recipes

class Ingredient(BaseModel):
    name: str = Field(description="The food item name (e.g., 'carrot', 'corn')")
    quantity_g: Optional[float] = Field(
        default=None,
        description=(
            "Weight in grams, or null if the user gave no quantity. "
            "ONLY set a number when the user explicitly stated an amount "
            "(e.g. '200g of corn', '2 chicken breasts'). "
            "If the user says 'I have broccoli' with no amount → null. "
            "DO NOT guess or estimate a quantity."
        )
    )

class RecipeSearchParams(BaseModel):
    query_text: str = Field(
        description=(
            "Keywords for the recipe database search. "
            "ONLY include ingredient names or dish names — nothing else. "
            "Strip out words like 'recipe', 'high protein', 'healthy', 'light', 'vegan', 'quick', etc. "
            "These are nutrition/diet descriptors that won't match anything in the database. "
            "CORRECT examples: 'chicken', 'corn salsa', 'banana muffins', 'broccoli stir fry'. "
            "WRONG examples: 'high protein chicken recipe', 'healthy vegan dessert', 'light meal ideas'."
        )
    )
    max_calories: Optional[int] = Field(
        default=None,
        description=(
            "Upper calorie limit per serving as an integer, or null. "
            "Extract from explicit mentions like 'under 500 calories'. "
            "If the user says 'light meal' use 500. If 'hungry' or 'big meal' use 1000. "
            "Use null (NOT the string 'None') if no calorie constraint is implied."
        )
    )
    min_protein_g: Optional[int] = Field(
        default=None,
        description=(
            "Minimum protein in grams as an integer, or null. "
            "Use 30 if user mentions strength training or muscle gain. "
            "Use 20 for general fitness goals. "
            "Use null (NOT the string 'None') if protein is not relevant."
        )
    )
    available_ingredients: Optional[List[Ingredient]] = Field(
        default=None,
        description=(
            "Ingredients the user already has, as a list of objects. "
            "Each object MUST have 'name' (string) and 'quantity_g' (number). "
            "Example: [{\"name\": \"corn\", \"quantity_g\": 200}]. "
            "Do NOT use a flat dict like {\"corn\": 200}."
        )
    )

    @field_validator("max_calories", "min_protein_g", mode="before")
    @classmethod
    def coerce_none_string(cls, v):
        if isinstance(v, str) and v.strip().lower() in ("none", "null", ""):
            return None
        return v

    @field_validator("available_ingredients", mode="before")
    @classmethod
    def coerce_ingredient_dict(cls, v):
        # [{"name": "corn", "quantity_g": 200}]
        if isinstance(v, dict):
            v = [{"name": k, "quantity_g": float(qty)} for k, qty in v.items()]
        # Strip blank/zero entries
        if isinstance(v, list):
            v = [i for i in v if isinstance(i, dict) and i.get("name", "").strip()]
            return v if v else None
        return v


@tool(args_schema=RecipeSearchParams)
def find_recipes(
    query_text: str,
    max_calories: Optional[int] = None,
    min_protein_g: Optional[int] = None,
    available_ingredients: Optional[List[Ingredient]] = None,
):
    """
    Search the recipe database using parameters extracted from the user's request.
    Always call this tool when the user wants recipe suggestions.
    """
    print("\n--- RECIPE SEARCH TRIGGERED ---")
    print(f"  Query      : {query_text}")
    print(f"  Max cal    : {max_calories} kcal")
    print(f"  Min protein: {min_protein_g} g")
    if available_ingredients:
        pantry_display = [
            {"name": i.name, "quantity_g": i.quantity_g}
            for i in available_ingredients
        ]
        print(f"  Pantry     : {pantry_display}")

    results_raw = search_recipes.invoke({
        "query_text": query_text,
        "max_calories": max_calories
    })

    if results_raw == "No recipes found matching those criteria.":
        return results_raw
    
    if min_protein_g:
        try:
            recipes = json.loads(results_raw)
            filtered = []
            for r in recipes:
                protein_str = r.get("nutrition", {}).get("proteinContent", "0")
                protein_val = float("".join(c for c in protein_str if c.isdigit() or c == "."))
                if protein_val >= min_protein_g:
                    filtered.append(r)
            return json.dumps(filtered) if filtered else "No recipes matched the protein requirement."
        except (json.JSONDecodeError, ValueError):
            pass

    return results_raw

SYSTEM_PROMPT = """You are a helpful nutrition and cooking assistant.

When a user asks for recipe ideas:
1. Call the `find_recipes` tool with parameters extracted from their message.
2. Extract `max_calories` and `min_protein_g` from context clues, not just explicit numbers.
3. List the user's available ingredients in `available_ingredients` as a list of objects.
4. After receiving results, summarise the top recipes in a friendly, concise way.

Parameter extraction rules:
- "under X calories" → max_calories = X
- "light / healthy" → max_calories = 500
- "hungry / big meal" → max_calories = 1000
- "post workout / strength training / leg day" → min_protein_g = 30
- "high protein" → min_protein_g = 25
- Available ingredients → available_ingredients list, e.g. [{"name": "corn", "quantity_g": 200}]
- Query can ONLY includes name of recipe or ingredients name, e.g "corn taco".

CRITICAL RULES:
1. You must ONLY suggest recipes provided by the `find_recipes` tool. 
2. If the tool returns "No recipes found", you MUST tell the user you couldn't find anything in the database. 
3. NEVER invent recipes or use your own internal knowledge to suggest meals.
4. Use the specific titles and nutrition facts provided in the tool's JSON output.
"""

def run_agent(user_input: str) -> str:
    llm = ChatOllama(model="llama3.1", temperature=0)
    tools = [find_recipes]
    llm_with_tools = llm.bind_tools(tools)
    tool_map = {t.name: t for t in tools}

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_input),
    ]

    for _ in range(5):  
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        tool_calls = response.tool_calls

        if not tool_calls and response.content:
            try:
                raw = re.sub(r"```(?:json)?|```", "", response.content).strip()
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and "name" in parsed:
                    tool_calls = [{
                        "name": parsed["name"],
                        "args": parsed.get("parameters") or parsed.get("args", {}),
                        "id": "fallback-0"
                    }]
            except (json.JSONDecodeError, KeyError):
                pass

        if not tool_calls:
            return response.content

        for call in tool_calls:
            tool_fn = tool_map.get(call["name"])
            if tool_fn:
                result = tool_fn.invoke(call["args"])
                messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))

    return "Agent loop limit reached without a final answer."


if __name__ == "__main__":
    print("Recipe Agent started. Type 'quit' or 'exit' to stop.")
    
    while True:
        try:
            user_input = input("\nUSER: ")
            if user_input.strip().lower() in ['quit', 'exit']:
                print("Exiting agent...")
                break
                
            if not user_input.strip():
                continue

            print(f"\n")
            
            answer = run_agent(user_input)
            
            print(f"\nASSISTANT: {answer}\n")
            
        except KeyboardInterrupt:
            print("\nExiting agent...")
            break
        except Exception as e:
            print(f"\nAn error occurred: {e}")