import cloudscraper
from bs4 import BeautifulSoup

url = "https://www.allrecipes.com/ingredients-a-z-6740416"


scraper = cloudscraper.create_scraper(
    browser={
        "browser": "chrome",
        "platform": "windows",
        "mobile": False
    }
)

response = scraper.get(url, timeout=15)

print("Status Code:", response.status_code)
if response.status_code != 200:
    print("Request failed!")
    exit()

soup = BeautifulSoup(response.text, "html.parser")
ingredients = soup.select("main ul li a[href*='/recipes/']")

for a in ingredients:
    name = a.get_text(strip=True)
    href = a.get("href")
    print(name, ":", href)

with open("data/category_links.txt", "w", encoding="utf-8") as f:
    for a in ingredients:
        href = a.get("href")
        if href:
            f.write(href + "\n")

print("Saved", len(ingredients), "category links.")