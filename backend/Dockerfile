FROM public.ecr.aws/docker/library/python:3.12-slim
WORKDIR /opt/cfo
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .
ENV PYTHONDONTWRITEBYTECODE=1 HOME=/tmp
USER 1001
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
