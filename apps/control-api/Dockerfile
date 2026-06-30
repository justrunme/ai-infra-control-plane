FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/control-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/control-api/app ./app
COPY governance ./governance

# Run as a non-root user (GID 0 for OpenShift compatibility) to match the
# runAsNonRoot security context enforced by the Helm chart.
RUN useradd --uid 10001 --gid 0 --no-create-home --shell /usr/sbin/nologin app \
    && chown -R 10001:0 /app
USER 10001

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
