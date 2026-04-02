import json
from bs4 import BeautifulSoup
import cloudscraper
import re


header= {"User-Agent": "Mozilla/5.0(Windows NT 10.0; Win64; x64)"}
scraper = cloudscraper.create_scraper()


def extract_jsonLD(html):
    soup = BeautifulSoup(html, "html.parser")
    for s in soup.find_all("script", type = "application/ld+json"):
        try:
            if s.string is None:
                continue
            data = json.loads(s.string)

            # if it is list type
            if isinstance(data,list):
                for item in data:
                    types = item.get("@type", [])
                    # check if @type contain Recipe
                    if isinstance(types,list) and "Recipe" in types:
                        return item
            # check if it is dirct type
            elif isinstance(data, dict):
                types = data.get("@type", [])
                if isinstance(types,list) and "Recipe" in types:
                    return data
                if isinstance(types, str) and types == "Recipe":
                    return data
        
        except:
            pass
    
    return None

def parse_recipe(data,html,url):
    recipe ={}
    recipe["title"] =data.get("name", "")
    recipe["ingredients"] = data.get("recipeIngredient", [])

    steps = []
    inst = data.get("recipeInstructions", [])

    if isinstance(inst, list):
        for step in inst:
            if isinstance(step,dict):
                steps.append(step.get("text","").strip())
            else:
                steps.append(str(step).strip())
    else:
        steps.append(str(inst).strip())
    
    recipe["steps"] = steps

    #extract image url
    image = data.get("image", "")
    if isinstance(image, str):
        recipe["image"] = image
    elif isinstance(image, list) and len(image) > 0:
        recipe["image"] = image[0]
    elif isinstance(image, dict) and "url" in image:
        recipe["image"] = image["url"]
    else:
        recipe["image"] = ""

# find nutrition fact and normalize values

    nutrition_fact = {}
    if "nutrition" in data and isinstance(data["nutrition"], dict):
        for key, raw_value in data["nutrition"].items():
            # skip the type field
            if key == "@type":
                continue

            text_val = str(raw_value).lower()
            # extract the first number
            match = re.search(r"[\d.]+", text_val)
            if not match:
                continue

            num = float(match.group())

            # convert mg to g
            if "mg" in text_val:
                num = num / 1000.0

            nutrition_fact[key] = round(num, 3)

    recipe["nutrition"] = nutrition_fact


    recipe["total_time"]=data.get("totalTime","")
    recipe["servings"] = data.get("recipeYield","")
    recipe["source_url"] = url

    return recipe

count = 0 ## cal the num of output data

with open("data/recipe_links.txt","r") as f:
    urls = f.read().splitlines()

with open("data/recipes.jsonl", "w", encoding="utf-8") as out:
    for url in urls:
        print("extract:", url)
        try:
            resp = scraper.get(url, headers= header, timeout = 10)
            jsonld = extract_jsonLD(resp.text)
            if jsonld:
                rec = parse_recipe(jsonld,resp.text, url)
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                count +=1
        except Exception as e:
            print("error:", e)

        

print("finished:", count)


    
