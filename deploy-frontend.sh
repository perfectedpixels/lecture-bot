#!/usr/bin/env bash
# Deploy lecture-bot's React frontend to S3 + CloudFront, with CloudFront
# proxying /api/* to the already-deployed App Runner service (run
# deploy-apprunner.sh FIRST — this script looks up its URL automatically).
#
# Single-domain design: the browser only ever talks to lecturebot.perfectpixels.com.
# CloudFront serves static assets from S3 for everything else, and forwards
# /api/* to App Runner as a same-origin path — no CORS needed, no separate
# API domain/cert to manage.
#
# RUN THIS WITH CREDENTIALS FOR ACCOUNT 582234715800 (same as deploy-apprunner.sh):
#   aws sts get-caller-identity   # should show 582234715800
#   bash deploy-frontend.sh
#
# Requires: aws cli, node/npm, and the App Runner service already deployed.
#
# NOTE: this script is new and has not been run/verified end-to-end (no AWS
# CLI available in the environment that wrote it). Read through the AWS CLI
# calls before trusting a fully unattended run for the first time — in
# particular, the ACM certificate step requires you to add a DNS record in
# GoDaddy partway through and cannot proceed until that record has propagated
# and ACM has validated it, which can take anywhere from a minute to ~30.
set -euo pipefail

REGION=us-east-1   # ACM certs for CloudFront MUST be in us-east-1, regardless of where anything else lives
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
DOMAIN=lecturebot.perfectpixels.com
BUCKET="lecture-bot-frontend-${ACCOUNT}"
APPRUNNER_SERVICE=lecture-bot-api
OAC_NAME=lecture-bot-frontend-oac
CF_COMMENT="lecture-bot frontend"

# AWS-managed CloudFront policy IDs (constant across all accounts):
CACHING_OPTIMIZED=658327ea-f89d-4fab-a63d-7e88639e58f6      # long-lived caching for the static site
CACHING_DISABLED=4135ea2d-6df8-44a3-9df3-4b5a84be39ad        # never cache /api/*
ORIGIN_REQUEST_ALL_VIEWER=216adef6-5c7f-47e4-b989-5492eafa07d3  # forward all headers/cookies/query strings to the API origin

echo "Account=$ACCOUNT Region=$REGION Domain=$DOMAIN"
[ "$ACCOUNT" = "582234715800" ] || echo "WARNING: expected account 582234715800 (where the App Runner service lives)"

# 0) Look up the already-deployed App Runner service URL
APPRUNNER_ARN=$(aws apprunner list-services --region $REGION --query "ServiceSummaryList[?ServiceName=='${APPRUNNER_SERVICE}'].ServiceArn | [0]" --output text)
if [ "$APPRUNNER_ARN" = "None" ] || [ -z "$APPRUNNER_ARN" ]; then
  echo "ERROR: App Runner service '${APPRUNNER_SERVICE}' not found — run deploy-apprunner.sh first." >&2
  exit 1
fi
APPRUNNER_URL=$(aws apprunner describe-service --region $REGION --service-arn "$APPRUNNER_ARN" --query "Service.ServiceUrl" --output text)
echo "App Runner origin: $APPRUNNER_URL"

# 1) S3 bucket for the built static site (private — CloudFront reads it via OAC, never public)
if ! aws s3api head-bucket --bucket "$BUCKET" >/dev/null 2>&1; then
  aws s3api create-bucket --bucket "$BUCKET" --region $REGION >/dev/null
  aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" >/dev/null
fi

# 2) ACM certificate for the custom domain (CloudFront requires it in us-east-1).
#    DNS validation — this is the one step that needs a manual GoDaddy edit.
EXISTING_CERT=$(aws acm list-certificates --region $REGION --query "CertificateSummaryList[?DomainName=='${DOMAIN}'].CertificateArn | [0]" --output text)
if [ "$EXISTING_CERT" = "None" ] || [ -z "$EXISTING_CERT" ]; then
  CERT_ARN=$(aws acm request-certificate --region $REGION --domain-name "$DOMAIN" --validation-method DNS --query CertificateArn --output text)
  echo "Requested ACM certificate: $CERT_ARN"
else
  CERT_ARN="$EXISTING_CERT"
  echo "Reusing existing ACM certificate: $CERT_ARN"
fi

# ACM needs a few seconds to generate the validation record after a fresh request.
sleep 5
RECORD_NAME=$(aws acm describe-certificate --region $REGION --certificate-arn "$CERT_ARN" --query "Certificate.DomainValidationOptions[0].ResourceRecord.Name" --output text)
RECORD_VALUE=$(aws acm describe-certificate --region $REGION --certificate-arn "$CERT_ARN" --query "Certificate.DomainValidationOptions[0].ResourceRecord.Value" --output text)
CERT_STATUS=$(aws acm describe-certificate --region $REGION --certificate-arn "$CERT_ARN" --query "Certificate.Status" --output text)

if [ "$CERT_STATUS" != "ISSUED" ]; then
  # GoDaddy's "Name" field wants the label relative to perfectpixels.com, not
  # the full record name ACM returns — strip the trailing ".perfectpixels.com."
  GODADDY_NAME="${RECORD_NAME%.perfectpixels.com.}"
  echo
  echo "=========================================================================="
  echo "ADD THIS DNS RECORD IN GODADDY (perfectpixels.com → DNS), then re-run this script:"
  echo "  Type:  CNAME"
  echo "  Name:  ${GODADDY_NAME}"
  echo "  Value: ${RECORD_VALUE}"
  echo "  TTL:   600 (or default)"
  echo "=========================================================================="
  echo
  echo "Waiting up to ~15 min for ACM to validate (checks every 30s; safe to Ctrl-C and re-run this script later — it's idempotent)…"
  for i in $(seq 1 30); do
    CERT_STATUS=$(aws acm describe-certificate --region $REGION --certificate-arn "$CERT_ARN" --query "Certificate.Status" --output text)
    echo "  [$i] $CERT_STATUS"
    [ "$CERT_STATUS" = "ISSUED" ] && break
    sleep 30
  done
  if [ "$CERT_STATUS" != "ISSUED" ]; then
    echo "Certificate still not ISSUED — add the DNS record above if you haven't, then re-run this script." >&2
    exit 1
  fi
fi
echo "Certificate ISSUED: $CERT_ARN"

# 3) CloudFront Origin Access Control (lets CloudFront read the private S3 bucket)
OAC_ID=$(aws cloudfront list-origin-access-controls --query "OriginAccessControlList.Items[?Name=='${OAC_NAME}'].Id | [0]" --output text)
if [ "$OAC_ID" = "None" ] || [ -z "$OAC_ID" ]; then
  OAC_ID=$(aws cloudfront create-origin-access-control --origin-access-control-config "{
    \"Name\": \"${OAC_NAME}\",
    \"OriginAccessControlOriginType\": \"s3\",
    \"SigningBehavior\": \"always\",
    \"SigningProtocol\": \"sigv4\"
  }" --query "OriginAccessControl.Id" --output text)
fi

# 4) CloudFront distribution: S3 origin (default behavior) + App Runner origin (/api/* behavior)
EXISTING_DIST=$(aws cloudfront list-distributions --query "DistributionList.Items[?Comment=='${CF_COMMENT}'].Id | [0]" --output text 2>/dev/null || echo "None")
if [ "$EXISTING_DIST" = "None" ] || [ -z "$EXISTING_DIST" ]; then
  DIST_CONFIG=$(
    BUCKET="$BUCKET" REGION="$REGION" APPRUNNER_URL="$APPRUNNER_URL" DOMAIN="$DOMAIN" CERT_ARN="$CERT_ARN" \
    OAC_ID="$OAC_ID" CACHING_OPTIMIZED="$CACHING_OPTIMIZED" CACHING_DISABLED="$CACHING_DISABLED" \
    ORIGIN_REQUEST_ALL_VIEWER="$ORIGIN_REQUEST_ALL_VIEWER" CF_COMMENT="$CF_COMMENT" \
    python3 -c '
import json, os, time

o = os.environ
config = {
    "CallerReference": str(time.time()),
    "Comment": o["CF_COMMENT"],
    "DefaultRootObject": "index.html",
    "Enabled": True,
    "Aliases": {"Quantity": 1, "Items": [o["DOMAIN"]]},
    "ViewerCertificate": {
        "ACMCertificateArn": o["CERT_ARN"],
        "SSLSupportMethod": "sni-only",
        "MinimumProtocolVersion": "TLSv1.2_2021",
    },
    "Origins": {
        "Quantity": 2,
        "Items": [
            {
                "Id": "s3-frontend",
                "DomainName": "{}.s3.{}.amazonaws.com".format(o["BUCKET"], o["REGION"]),
                "S3OriginConfig": {"OriginAccessIdentity": ""},
                "OriginAccessControlId": o["OAC_ID"],
            },
            {
                "Id": "apprunner-api",
                "DomainName": o["APPRUNNER_URL"],
                "CustomOriginConfig": {
                    "HTTPPort": 80,
                    "HTTPSPort": 443,
                    "OriginProtocolPolicy": "https-only",
                    "OriginSslProtocols": {"Quantity": 1, "Items": ["TLSv1.2"]},
                },
            },
        ],
    },
    "DefaultCacheBehavior": {
        "TargetOriginId": "s3-frontend",
        "ViewerProtocolPolicy": "redirect-to-https",
        "CachePolicyId": o["CACHING_OPTIMIZED"],
        "Compress": True,
    },
    "CacheBehaviors": {
        "Quantity": 1,
        "Items": [
            {
                "PathPattern": "/api/*",
                "TargetOriginId": "apprunner-api",
                "ViewerProtocolPolicy": "https-only",
                "AllowedMethods": {
                    "Quantity": 7,
                    "Items": ["GET", "HEAD", "OPTIONS", "PUT", "PATCH", "POST", "DELETE"],
                    "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
                },
                "CachePolicyId": o["CACHING_DISABLED"],
                "OriginRequestPolicyId": o["ORIGIN_REQUEST_ALL_VIEWER"],
                "Compress": True,
            }
        ],
    },
    "CustomErrorResponses": {
        "Quantity": 2,
        "Items": [
            {"ErrorCode": 403, "ResponseCode": "200", "ResponsePagePath": "/index.html", "ErrorCachingMinTTL": 10},
            {"ErrorCode": 404, "ResponseCode": "200", "ResponsePagePath": "/index.html", "ErrorCachingMinTTL": 10},
        ],
    },
}
print(json.dumps(config))
'
  )
  echo "$DIST_CONFIG" > /tmp/cf-dist-config.json
  DIST_RESULT=$(aws cloudfront create-distribution --distribution-config file:///tmp/cf-dist-config.json)
  DIST_ID=$(echo "$DIST_RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin)['Distribution']['Id'])")
  DIST_DOMAIN=$(echo "$DIST_RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin)['Distribution']['DomainName'])")
else
  DIST_ID="$EXISTING_DIST"
  DIST_DOMAIN=$(aws cloudfront get-distribution --id "$DIST_ID" --query "Distribution.DomainName" --output text)
  echo "Reusing existing CloudFront distribution: $DIST_ID"
fi

# 5) Bucket policy: allow ONLY this CloudFront distribution (via OAC) to read the bucket
aws s3api put-bucket-policy --bucket "$BUCKET" --policy "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [
    {
      \"Sid\": \"AllowCloudFrontServicePrincipal\",
      \"Effect\": \"Allow\",
      \"Principal\": {\"Service\": \"cloudfront.amazonaws.com\"},
      \"Action\": \"s3:GetObject\",
      \"Resource\": \"arn:aws:s3:::${BUCKET}/*\",
      \"Condition\": {\"StringEquals\": {\"AWS:SourceArn\": \"arn:aws:cloudfront::${ACCOUNT}:distribution/${DIST_ID}\"}}
    }
  ]
}" >/dev/null

# 6) Build the frontend and sync it to S3
(cd frontend && npm install && npm run build)
aws s3 sync frontend/dist/ "s3://${BUCKET}/" --delete

# 7) Invalidate the CloudFront cache so the new build is served immediately
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" >/dev/null

echo
echo "=========================================================================="
echo "DONE."
echo "CloudFront distribution: https://${DIST_DOMAIN} (works immediately)"
echo
if [ -z "${EXISTING_DIST:-}" ] || [ "$EXISTING_DIST" = "None" ]; then
  echo "FINAL STEP — add this DNS record in GoDaddy (perfectpixels.com → DNS):"
  echo "  Type:  CNAME"
  echo "  Name:  lecturebot"
  echo "  Value: ${DIST_DOMAIN}"
  echo "  TTL:   600 (or default)"
  echo
  echo "Once that propagates (15-60 min, sometimes longer), the app is live at:"
fi
echo "  https://${DOMAIN}"
echo "=========================================================================="
