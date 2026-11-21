import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

url = os.environ.get("NEWS_FETCH_URL", "http://news-service:8080/fetch")
token = os.environ["ADMIN_TOKEN"]

request = Request(
    url,
    data=b"",
    headers={
        "X-Admin-Token": token,
        "Accept": "application/json",
    },
    method="POST",
)

try:
    with urlopen(request, timeout=600) as response:
        body = response.read().decode("utf-8", errors="replace")
        print(f"Fetch endpoint returned HTTP {response.status}")
        print(body)
        if not 200 <= response.status < 300:
            sys.exit(1)
except HTTPError as error:
    print(f"Fetch endpoint returned HTTP {error.code}", file=sys.stderr)
    print(error.read().decode("utf-8", errors="replace"), file=sys.stderr)
    sys.exit(1)
