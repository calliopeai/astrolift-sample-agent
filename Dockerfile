# astrolift-sample-agent — minimal real Python agent fixture.
FROM python:3.12-slim

# Build metadata surfaced by /debug and the startup banner.
ARG GIT_SHA=dev
ARG BUILT_AT=unknown
ARG IMAGE_REF=docker.io/calliopeai/astrolift-sample-agent:dev
ENV GIT_SHA=${GIT_SHA} \
    BUILT_AT=${BUILT_AT} \
    IMAGE_REF=${IMAGE_REF} \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Stdlib-only today, but install from requirements.txt so a future dep is
# a one-line change with no Dockerfile churn.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY agent/ ./agent/

# Service-family agents listen here; Task-family runs ignore it.
EXPOSE 8000

# Mode-aware entrypoint: RUN_FAMILY=service serves /health+/debug and
# stays up; anything else performs once and exits 0.
ENTRYPOINT ["python", "-m", "agent.main"]
