## Run locally with Docker
docker build -t instrument-agent .
docker run --rm -p 8080:8080 --env-file .env instrument-agent