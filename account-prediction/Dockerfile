# SME balance forecast service.
# Red Hat UBI Python image: runs as a non-root user, which OpenShift requires.
FROM registry.access.redhat.com/ubi9/python-312:latest

WORKDIR /opt/app-root/src

# dependencies first, so code changes do not reinstall them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data

# OpenShift starts the container with a random user id in group 0: give group 0 the owner's rights,
# so uploaded statements can be written to the data folder.
USER 0
RUN chgrp -R 0 /opt/app-root/src && chmod -R g=u /opt/app-root/src
USER 1001

# LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, ... are set at deploy time (see README); never bake tokens into the image.
ENV DATA_DIR=/opt/app-root/src/data \
    PYTHONUNBUFFERED=1

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
