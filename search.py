from typing import Optional, Type
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from elasticsearch import Elasticsearch


# ── Input Schema ──────────────────────────────────────────────────────────────

class NutrientRange(BaseModel):
    min: Optional[float] = Field(None, description="Minimum value (inclusive)")
    max: Optional[float] = Field(None, description="Maximum value (inclusive)")


class RecipeSearchInput(BaseModel):
    """All fields are optional — combine freely to narrow results."""

    # Full-text / keyword filters
    title: Optional[str] = Field(None, description="Partial title to search for (full-text)")
    ingredients: Optional[list[str]] = Field(
        None, description="Ingredients that must appear in the recipe (e.g. ['chicken', 'garlic'])"
    )

    # Numeric / range filters (per-serving values stored in the DB)
    calories: Optional[NutrientRange] = Field(None, description="Calorie range, e.g. {'min': 100, 'max': 400}")
    protein: Optional[NutrientRange] = Field(None, description="Protein (g) range")
    fat: Optional[NutrientRange] = Field(None, description="Total fat (g) range")
    saturated_fat: Optional[NutrientRange] = Field(None, description="Saturated fat (g) range")
    carbohydrates: Optional[NutrientRange] = Field(None, description="Carbohydrate (g) range")
    fiber: Optional[NutrientRange] = Field(None, description="Fiber (g) range")
    sugar: Optional[NutrientRange] = Field(None, description="Sugar (g) range")
    sodium: Optional[NutrientRange] = Field(
        None, description="Sodium (g) range — note: stored in grams in this DB"
    )

    # Result control
    max_results: int = Field(10, description="Maximum number of recipes to return (default 10)")


# ── Elasticsearch query builder ───────────────────────────────────────────────

# Maps schema field names → Elasticsearch document field paths
NUTRIENT_FIELD_MAP = {
    "calories":      "nutrition.calories",
    "protein":       "nutrition.proteinContent",
    "fat":           "nutrition.fatContent",
    "saturated_fat": "nutrition.saturatedFatContent",
    "carbohydrates": "nutrition.carbohydrateContent",
    "fiber":         "nutrition.fiberContent",
    "sugar":         "nutrition.sugarContent",
    "sodium":        "nutrition.sodiumContent",
}


def build_recipe_query(params: RecipeSearchInput) -> dict:
    """Convert a RecipeSearchInput into an Elasticsearch bool query."""
    must_clauses = []
    filter_clauses = []

    # ── Full-text: title ──────────────────────────────────────────────────────
    if params.title:
        must_clauses.append({
            "match": {
                "title": {
                    "query": params.title,
                    "fuzziness": "AUTO",   # tolerates minor typos
                }
            }
        })

    # ── Full-text: ingredients ────────────────────────────────────────────────
    # Each requested ingredient must appear at least once in the ingredients list.
    if params.ingredients:
        for ingredient in params.ingredients:
            must_clauses.append({
                "match": {
                    "ingredients": {
                        "query": ingredient,
                        "fuzziness": "AUTO",
                        "operator": "and",
                    }
                }
            })

    # ── Numeric ranges: nutrients ─────────────────────────────────────────────
    for field_name, es_path in NUTRIENT_FIELD_MAP.items():
        range_val: Optional[NutrientRange] = getattr(params, field_name)
        if range_val is None:
            continue

        range_clause: dict = {}
        if range_val.min is not None:
            range_clause["gte"] = range_val.min
        if range_val.max is not None:
            range_clause["lte"] = range_val.max

        if range_clause:
            filter_clauses.append({"range": {es_path: range_clause}})

    # ── Assemble bool query ───────────────────────────────────────────────────
    bool_query: dict = {}
    if must_clauses:
        bool_query["must"] = must_clauses
    if filter_clauses:
        bool_query["filter"] = filter_clauses

    # If nothing was specified, return all documents
    if not bool_query:
        return {"query": {"match_all": {}}, "size": params.max_results}

    return {"query": {"bool": bool_query}, "size": params.max_results}


# ── LangChain Tool ────────────────────────────────────────────────────────────

class RecipeSearchTool(BaseTool):
    """LangChain tool that searches an Elasticsearch recipe database."""

    name: str = "recipe_search"
    description: str = (
        "Search a recipe database by title, ingredients, and/or nutritional ranges "
        "(calories, protein, fat, carbohydrates, fiber, sugar, sodium, saturated fat). "
        "All parameters are optional — combine them to narrow results."
    )
    args_schema: Type[BaseModel] = RecipeSearchInput

    # Injected at construction time
    es_client: Elasticsearch
    index_name: str = "recipes"

    class Config:
        arbitrary_types_allowed = True  # allows Elasticsearch client as a field

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _format_hit(self, hit: dict) -> dict:
        """Return a clean summary dict from an ES hit."""
        src = hit.get("_source", {})
        nutrition = src.get("nutrition", {})
        return {
            "title":       src.get("title"),
            "servings":    src.get("servings"),
            "total_time":  src.get("total_time"),
            "source_url":  src.get("source_url"),
            "ingredients": src.get("ingredients", []),
            "steps":       src.get("steps", []),
            "nutrition": {
                "calories":      nutrition.get("calories"),
                "protein_g":     nutrition.get("proteinContent"),
                "fat_g":         nutrition.get("fatContent"),
                "saturated_fat_g": nutrition.get("saturatedFatContent"),
                "carbs_g":       nutrition.get("carbohydrateContent"),
                "fiber_g":       nutrition.get("fiberContent"),
                "sugar_g":       nutrition.get("sugarContent"),
                "sodium_g":      nutrition.get("sodiumContent"),
            },
            "score": hit.get("_score"),
        }

    # ── Tool entry points ─────────────────────────────────────────────────────

    def _run(self, **kwargs) -> list[dict]:
        params = RecipeSearchInput(**kwargs)
        query = build_recipe_query(params)
        response = self.es_client.search(index=self.index_name, body=query)
        hits = response.get("hits", {}).get("hits", [])
        return [self._format_hit(h) for h in hits]

    async def _arun(self, **kwargs) -> list[dict]:
        # Wire up an async ES client here if needed; falls back to sync for now.
        return self._run(**kwargs)


# ── Usage example ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    es = Elasticsearch("http://localhost:9200")

    tool = RecipeSearchTool(es_client=es, index_name="recipes")

    # Example 1 — low-calorie turkey recipes
    results = tool._run(
        title="turkey",
        calories={"min": 50, "max": 300},
        protein={"min": 15},
        max_results=5,
    )
    for r in results:
        print(r["title"], "|", r["nutrition"])

    # Example 2 — recipes containing chicken and garlic, under 500 calories
    results = tool._run(
        ingredients=["chicken", "garlic"],
        calories={"max": 500},
        max_results=10,
    )
    for r in results:
        print(r["title"])

    # Example 3 — high-fiber, low-sugar soups
    results = tool._run(
        title="soup",
        fiber={"min": 4},
        sugar={"max": 3},
    )
    for r in results:
        print(r["title"], "| fiber:", r["nutrition"]["fiber_g"])