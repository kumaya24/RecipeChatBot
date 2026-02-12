import json
from elasticsearch import Elasticsearch, helpers
from argparse import ArgumentParser

def get_args():
    args = ArgumentParser()
    args.add_argument('--json_path', type=str, default='data/recipes.jsonl')
    return args.parse_args()

es = Elasticsearch(
    "http://localhost:9200",
    request_timeout=60,
    verify_certs=False
)

def load_data():
    args = get_args()

    actions = []
    with open(args.json_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                recipe = json.loads(line)
                action = {
                    "_index": "recipes",
                    "_source": recipe
                }
                actions.append(action)

    print(f"Sending {len(actions)} recipes to Elasticsearch...")
    helpers.bulk(es, actions)
    print("Success!")

if __name__ == "__main__":
    if es.ping():
        load_data()
    else:
        print("can not connect to elastic search, check if docker is runnign")