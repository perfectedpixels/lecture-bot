#!/usr/bin/env bash
# Deploy lecture-bot's methodology API to AWS App Runner (HTTPS URL) in the
# account that owns its KB (HHYCUJH32J = account 582234715800, us-east-1).
#
# RUN THIS WITH CREDENTIALS FOR THAT ACCOUNT (not the ux-team-kb account):
#   aws sts get-caller-identity   # should show 582234715800
#   bash deploy-apprunner.sh
#
# Outputs the service URL:
#  - Paste it into ux-team-kb as LECTURE_BOT_API_URL (server-to-server consumer).
#  - It's also the origin deploy-frontend.sh points CloudFront's /api/* behavior
#    at, so the browser-facing app never talks to this URL directly.
#
# Reads CANVAS_API_TOKEN/CANVAS_BASE_URL/CANVAS_COURSE_IDS from .env (if
# present) to inject as secrets into the running container — never hardcoded
# here, never baked into the Docker image.
set -euo pipefail

REGION=us-east-1
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REPO=lecture-bot-api
SERVICE=lecture-bot-api
IMAGE_TAG="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/${REPO}:latest"
BOARDS_TABLE=lecture-bot-explore-boards

echo "Account=$ACCOUNT Region=$REGION"
[ "$ACCOUNT" = "582234715800" ] || echo "WARNING: expected account 582234715800 (where HHYCUJH32J lives)"

# Pull Canvas config from .env for the runtime env vars below (optional —
# homework-help just stays disabled if these aren't set).
if [ -f .env ]; then
  CANVAS_API_TOKEN=$(grep -E '^CANVAS_API_TOKEN=' .env | head -1 | cut -d= -f2-)
  CANVAS_BASE_URL=$(grep -E '^CANVAS_BASE_URL=' .env | head -1 | cut -d= -f2-)
  CANVAS_COURSE_IDS=$(grep -E '^CANVAS_COURSE_IDS=' .env | head -1 | cut -d= -f2-)
fi
CANVAS_BASE_URL="${CANVAS_BASE_URL:-https://canvas.uw.edu}"

# 1) ECR repo + image
aws ecr describe-repositories --region $REGION --repository-names $REPO >/dev/null 2>&1 \
  || aws ecr create-repository --region $REGION --repository-name $REPO >/dev/null
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
# App Runner runs x86_64 images. --provenance=false: modern Docker attaches a
# build-provenance attestation by default, which turns the pushed artifact
# into a multi-entry manifest list (image + attestation) instead of a plain
# single-platform manifest — App Runner can fail to resolve the real image
# out of that list (pulls "successfully" but the container never actually
# runs, no application logs at all). Same fix ux-team-kb's own deploy uses.
docker build --provenance=false --platform linux/amd64 -t "$IMAGE_TAG" .
docker push "$IMAGE_TAG"

# 2) Instance role: lets the running container call Bedrock (Retrieve + Claude on the KB)
INSTANCE_ROLE=lecture-bot-apprunner-instance
aws iam get-role --role-name $INSTANCE_ROLE >/dev/null 2>&1 || aws iam create-role --role-name $INSTANCE_ROLE \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"tasks.apprunner.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
aws iam put-role-policy --role-name $INSTANCE_ROLE --policy-name bedrock-kb-access --policy-document '{
  "Version":"2012-10-17",
  "Statement":[
    {"Sid":"Retrieve","Effect":"Allow","Action":["bedrock:Retrieve","bedrock:RetrieveAndGenerate"],"Resource":"*"},
    {"Sid":"Invoke","Effect":"Allow","Action":["bedrock:InvokeModel","bedrock:InvokeModelWithResponseStream"],"Resource":"*"}
  ]}'
INSTANCE_ROLE_ARN=$(aws iam get-role --role-name $INSTANCE_ROLE --query Role.Arn --output text)

# 2b) DynamoDB table for explore-canvas boards (shareable canvas snapshots)
aws dynamodb describe-table --region $REGION --table-name $BOARDS_TABLE >/dev/null 2>&1 \
  || aws dynamodb create-table --region $REGION --table-name $BOARDS_TABLE \
       --attribute-definitions AttributeName=pk,AttributeType=S AttributeName=sk,AttributeType=S \
       --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE \
       --billing-mode PAY_PER_REQUEST >/dev/null
BOARDS_TABLE_ARN=$(aws dynamodb describe-table --region $REGION --table-name $BOARDS_TABLE --query "Table.TableArn" --output text)

aws iam put-role-policy --role-name $INSTANCE_ROLE --policy-name boards-dynamodb-access --policy-document '{
  "Version":"2012-10-17",
  "Statement":[
    {"Sid":"BoardsTable","Effect":"Allow","Action":["dynamodb:PutItem","dynamodb:GetItem","dynamodb:UpdateItem","dynamodb:DeleteItem","dynamodb:Query"],"Resource":"'"$BOARDS_TABLE_ARN"'"}
  ]}'

# 3) Access role: lets App Runner pull the private ECR image
ACCESS_ROLE=lecture-bot-apprunner-ecr-access
aws iam get-role --role-name $ACCESS_ROLE >/dev/null 2>&1 || aws iam create-role --role-name $ACCESS_ROLE \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"build.apprunner.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
aws iam attach-role-policy --role-name $ACCESS_ROLE \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess >/dev/null 2>&1 || true
ACCESS_ROLE_ARN=$(aws iam get-role --role-name $ACCESS_ROLE --query Role.Arn --output text)

sleep 8  # let IAM propagate

# 4) Create (or update) the App Runner service
# Built via Python (not a raw heredoc) so CANVAS_API_TOKEN/etc. are properly
# JSON-escaped regardless of their contents, and CANVAS_* are only included
# when actually set in .env (homework-help just stays disabled otherwise).
SRC_JSON=$(
  IMAGE_TAG="$IMAGE_TAG" ACCESS_ROLE_ARN="$ACCESS_ROLE_ARN" BOARDS_TABLE="$BOARDS_TABLE" \
  CANVAS_API_TOKEN="${CANVAS_API_TOKEN:-}" CANVAS_BASE_URL="$CANVAS_BASE_URL" CANVAS_COURSE_IDS="${CANVAS_COURSE_IDS:-}" \
  python3 -c '
import json, os

env = {
    "BEDROCK_KNOWLEDGE_BASE_ID": "HHYCUJH32J",
    "AWS_REGION": "us-east-1",
    "BEDROCK_MODEL_ID": "us.anthropic.claude-sonnet-4-20250514-v1:0",
    "BOARDS_TABLE_NAME": os.environ["BOARDS_TABLE"],
    "CANVAS_BASE_URL": os.environ["CANVAS_BASE_URL"],
}
if os.environ.get("CANVAS_API_TOKEN"):
    env["CANVAS_API_TOKEN"] = os.environ["CANVAS_API_TOKEN"]
if os.environ.get("CANVAS_COURSE_IDS"):
    env["CANVAS_COURSE_IDS"] = os.environ["CANVAS_COURSE_IDS"]

src = {
    "ImageRepository": {
        "ImageIdentifier": os.environ["IMAGE_TAG"],
        "ImageRepositoryType": "ECR",
        "ImageConfiguration": {"Port": "8080", "RuntimeEnvironmentVariables": env},
    },
    "AutoDeploymentsEnabled": False,
    "AuthenticationConfiguration": {"AccessRoleArn": os.environ["ACCESS_ROLE_ARN"]},
}
print(json.dumps(src))
'
)

EXISTING=$(aws apprunner list-services --region $REGION --query "ServiceSummaryList[?ServiceName=='${SERVICE}'].ServiceArn | [0]" --output text)
if [ "$EXISTING" = "None" ] || [ -z "$EXISTING" ]; then
  aws apprunner create-service --region $REGION --service-name $SERVICE \
    --source-configuration "$SRC_JSON" \
    --instance-configuration "InstanceRoleArn=${INSTANCE_ROLE_ARN}" \
    --health-check-configuration "Protocol=HTTP,Path=/api/health,Interval=10,Timeout=10,HealthyThreshold=1,UnhealthyThreshold=10" \
    --query "Service.ServiceArn" --output text
else
  echo "service exists; updating image + env vars: $EXISTING"
  # update-service (not start-deployment) so changed env vars actually apply —
  # it triggers its own deployment of the new config, so no separate
  # start-deployment call is needed (that would just race it).
  aws apprunner update-service --region $REGION --service-arn "$EXISTING" \
    --source-configuration "$SRC_JSON" >/dev/null
fi

echo
echo "Waiting for service URL (App Runner build ~3-6 min)…"
ARN=$(aws apprunner list-services --region $REGION --query "ServiceSummaryList[?ServiceName=='${SERVICE}'].ServiceArn | [0]" --output text)
for i in $(seq 1 40); do
  S=$(aws apprunner describe-service --region $REGION --service-arn "$ARN" --query "Service.Status" --output text)
  URL=$(aws apprunner describe-service --region $REGION --service-arn "$ARN" --query "Service.ServiceUrl" --output text)
  echo "  [$i] $S  $URL"
  [ "$S" = "RUNNING" ] && break
  [ "$S" = "CREATE_FAILED" ] && { echo "FAILED — check App Runner logs"; exit 1; }
  sleep 15
done
echo
echo "DONE. LECTURE_BOT_API_URL = https://${URL}"
echo "Verify: curl https://${URL}/api/health"
