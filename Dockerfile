# Lecture-bot methodology API — container for AWS App Runner (or ECS/Fargate).
# Serves the FULL persona bot (its directives/behavior + KB retrieval) at
# POST /api/chat. Consumed server-to-server by ux-team-kb's orchestrator.
FROM python:3.12-slim

WORKDIR /app

# Only the API deps are needed at runtime (the persona bot uses boto3 + stdlib;
# voice/project-mapper imports in main.py are optional and degrade gracefully).
COPY api/requirements.txt /app/api/requirements.txt
RUN pip install --no-cache-dir -r /app/api/requirements.txt

# App code: api/ (main.py adds ../src to sys.path) + src/ + the small data
# files read at init/query time (learning cards + the Canvas homework-help
# grading-handbook rubric fallback in canvas_assignments.py).
COPY src/ /app/src/
COPY api/ /app/api/
COPY data/affinity_map.json /app/data/affinity_map.json
COPY data/teaching_concepts.json /app/data/teaching_concepts.json
# Whole grading dir, not just the handbook: also carries data/grading/calibration/,
# the per-assignment 4.0 anchors. Copying the directory means adding a new
# calibration file doesn't also require remembering to edit this Dockerfile.
COPY data/grading/ /app/data/grading/
# No data/portfolio_image_metadata.json here -- that dataset (and the images
# under data/portfolio_images/) was removed from the working tree. Not
# copying it is safe: LearningCardGenerator.__init__ (src/learning_card_generator.py)
# already checks Path(portfolio_metadata_path).exists() before loading it and
# degrades gracefully (portfolio-example enrichment on learning cards is
# simply unavailable, nothing else depends on this file).

# KB HHYCUJH32J lives in us-east-1; pin region so boto3 targets it.
# PYTHONUNBUFFERED: without this, Python fully buffers stdout when it isn't a
# TTY (i.e. always, in a container) — print() diagnostics (bot init success/
# failure, learning-card/voice degradation notices) silently vanish from
# `docker logs`/CloudWatch until the buffer fills or the process exits.
ENV PORT=8080 \
    PYTHONUNBUFFERED=1 \
    AWS_DEFAULT_REGION=us-east-1 \
    AWS_REGION=us-east-1 \
    BEDROCK_KNOWLEDGE_BASE_ID=HHYCUJH32J

EXPOSE 8080
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
