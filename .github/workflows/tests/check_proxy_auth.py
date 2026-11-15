"""Check protected models access with missing, wrong and active master keys."""
import json
import sys
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener


def check_auth(master_key, base_url="http://127.0.0.1:4000"):
    if not master_key:
        raise ValueError("An active master key is required")
    opener = build_opener(ProxyHandler({}))

    def request(key):
        headers = {"Authorization": "Bearer " + key} if key is not None else {}
        try:
            response = opener.open(Request(base_url + "/v1/models", headers=headers), timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    missing_status, missing_body = request(None)
    assert missing_status == 401 and isinstance(missing_body.get("error"), dict), \
        "Missing key must receive an authentication error"
    wrong_key = "sk-synthetic-wrong-key"
    if wrong_key == master_key:
        wrong_key += "-other"
    wrong_status, wrong_body = request(wrong_key)
    error = wrong_body.get("error")
    assert isinstance(error, dict), "Wrong key must receive a structured error"
    # LiteLLM rejects non-master keys with this error when virtual-key storage is absent.
    # https://github.com/BerriAI/litellm/blob/v1.108.3/litellm/proxy/auth/user_api_key_auth.py
    no_database = (wrong_status == 400 and error.get("type") == "no_db_connection"
                   and error.get("message") == "No connected db."
                   and str(error.get("code")) == "400")
    assert wrong_status == 401 or no_database, \
        f"Expected wrong-key rejection, got HTTP {wrong_status}"
    valid_status, valid_body = request(master_key)
    assert valid_status == 200 and isinstance(valid_body.get("data"), list), \
        "Active master key must successfully list models"


if __name__ == "__main__":
    check_auth(sys.stdin.read().rstrip("\r\n"))
    print("Protected models endpoint rejects missing/wrong keys and accepts the active key.")
