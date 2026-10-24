# AFAW tools image: the deterministic scripts, with no network service. Task 013 adds the
# read-only service image. Tagged with the commit by CI, never with "latest".
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 afaw

WORKDIR /app
COPY scripts/ scripts/
COPY state/schemas/ state/schemas/
COPY state/config.json state/config.json

USER afaw
ENTRYPOINT ["python", "-m"]
CMD ["scripts.build_state", "--help"]
