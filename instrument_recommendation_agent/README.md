## Run locally with Docker
docker build -t instrument-agent .
docker run --rm -p 8080:8080 --env-file .env instrument-agent

## Test with curl
```bash
curl --fail-with-body -sS http://localhost:8080/recommendations \
  -H 'Content-Type: application/json' \
  -d '{
    "account_id": "demo-account",
    "as_of": "2026-11-21",
    "official": {
      "safe_to_lock": [
        {"days": 30, "amount": 3000, "lowest_balance": 18000},
        {"days": 60, "amount": 1200, "lowest_balance": 16200},
        {"days": 90, "amount": 0, "lowest_balance": 15000}
      ]
    }
  }' | python3 -m json.tool
```