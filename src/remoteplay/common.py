import requests
from json import loads

PAPERSPACE_API = "https://api.paperspace.com/v1"


def check_state(machine_id, api_key):
    return request_get(machine_id, api_key)["state"] if machine_id else "unknown"


def request_get(path, api_key):
    response = requests.get(f"{PAPERSPACE_API}/machines/{path}", headers={
        "accept": "application/json",
        "authorization": f"Bearer {api_key}"
    })
    return loads(response.text)


def request_patch(path, api_key):
    response = requests.patch(f"{PAPERSPACE_API}/machines/{path}", headers={
        "accept": "application/json",
        "authorization": f"Bearer {api_key}"
    })
    return loads(response.text)

