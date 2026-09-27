FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH="/workspace/knowledge-base/extraction/src:/workspace/packages/aws_utils:/workspace/packages/utils"

RUN useradd \
    --create-home \
    --uid 10001 \
    appuser

WORKDIR /workspace

COPY knowledge-base/extraction/requirements.txt \
     /tmp/requirements.txt

RUN pip install \
    --require-hashes \
    --requirement /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY --chown=appuser:appuser \
    knowledge-base/extraction/src/ \
    knowledge-base/extraction/src/

COPY --chown=appuser:appuser \
    packages/aws_utils/aws_utils/ \
    packages/aws_utils/aws_utils/

COPY --chown=appuser:appuser \
    packages/utils/utils/ \
    packages/utils/utils/

USER appuser

WORKDIR /workspace/knowledge-base/extraction

CMD ["python", "src/main.py"]