FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Pinned supply-chain tools for in-process OCI policy materialization.
# Prefer Helm initContainer for production OCI pulls; these binaries cover
# standalone/docker-compose and CI image smoke tests.
ARG ORAS_VERSION=1.2.2
ARG COSIGN_VERSION=2.4.3
ARG TARGETARCH

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && arch="${TARGETARCH:-$(uname -m)}" \
    && if [ "$arch" = "amd64" ] || [ "$arch" = "x86_64" ]; then arch=amd64; \
       elif [ "$arch" = "arm64" ] || [ "$arch" = "aarch64" ]; then arch=arm64; \
       else arch=amd64; fi \
    && curl -fsSL "https://github.com/oras-project/oras/releases/download/v${ORAS_VERSION}/oras_${ORAS_VERSION}_linux_${arch}.tar.gz" \
       | tar -xz -C /usr/local/bin oras \
    && curl -fsSL "https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign-linux-${arch}" \
       -o /usr/local/bin/cosign \
    && chmod +x /usr/local/bin/oras /usr/local/bin/cosign \
    && rm -rf /var/lib/apt/lists/*

COPY apps/control-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/control-api/app ./app
COPY governance ./governance
COPY fleet ./fleet
COPY finops ./finops
COPY experiments/finops-recommendations ./experiments/finops-recommendations

# Run as a non-root user (GID 0 for OpenShift compatibility) to match the
# runAsNonRoot security context enforced by the Helm chart.
RUN useradd --uid 10001 --gid 0 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /var/lib/ai-control-plane \
    && chown -R 10001:0 /app /var/lib/ai-control-plane
USER 10001

ENV DATABASE_URL=sqlite:////var/lib/ai-control-plane/control-plane.db

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
