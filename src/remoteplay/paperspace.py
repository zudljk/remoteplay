import requests
from time import sleep
from json import loads

api_url = "https://api.paperspace.com/v1"


def _headers(api_key):
    return {"accept": "application/json", "authorization": f"Bearer {api_key}"}


def list_machines(api_key):
    # TODO: Support paging (attribute: nextPage)
    response = requests.get(f"{api_url}/machines", headers=_headers(api_key))
    return loads(response.text)["items"]


def start_machine(api_key, machine_id):
    headers = _headers(api_key)
    response = requests.get(f'{api_url}/machines/{machine_id}', headers=headers)
    json = loads(response.text)
    if json.get("state") != 'ready':
        response = requests.patch(f'{api_url}/machines/{machine_id}/start', headers=headers)
        json = loads(response.text)
        while json.get("state") != 'ready':
            sleep(5)
            response = requests.get(f'{api_url}/machines/{machine_id}', headers=headers)
            json = loads(response.text)


def stop_machine(api_key, machine_id, wait=False):
    headers = _headers(api_key)
    response = requests.get(f'{api_url}/machines/{machine_id}', headers=headers)
    json = loads(response.text)
    if json.get("state") == 'ready':
        response = requests.patch(f'{api_url}/machines/{machine_id}/stop', headers=headers)
        if not wait:
            return
        json = loads(response.text)
        while json.get("state") != 'off':
            sleep(5)
            response = requests.get(f'{api_url}/machines/{machine_id}', headers=headers)
            json = loads(response.text)

 