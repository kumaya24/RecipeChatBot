import requests
from bs4 import BeautifulSoup


header= {"User-Agent": "Mozilla/5.0(Windows NT 10.0; Win64; x64)"}

links = set() 
def extact_recipe_links(category_url):
    resp = requests.get(category_url, headers=header)
    soup = BeautifulSoup(resp.text,"html.parser")
    
    
    for a in soup.select("a[href*='/recipe/'] "):
        href =  a.get("href")
        if href and href.count("/") > 5:
            links.add(href)
    
    return links

all_links =set()

with open("data/category_links.txt", "r") as f:
    categories = f.read().splitlines()

for cat in categories:
    found = extact_recipe_links(cat)
    all_links.update(found)

with open("data/recipe_links.txt","w") as f:
    for r in all_links:
        f.write(r + "\n")


