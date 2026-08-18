# Lecture-Bot Custom Domain: lecturebot.perfectpixels.com

**Current architecture** (replaces the old Streamlit-Cloud/Railway setup this
doc used to describe): a single domain, `lecturebot.perfectpixels.com`, served
entirely by CloudFront —

- **Frontend**: React app built to static files, stored in a private S3
  bucket, served by CloudFront (default cache behavior).
- **API**: FastAPI on AWS App Runner (`deploy-apprunner.sh`). CloudFront
  forwards any request under `/api/*` to the App Runner origin as a second
  cache behavior — the browser never talks to the App Runner URL directly, so
  there's no CORS to configure and only one domain/certificate to manage.

Both are provisioned by scripts in this repo: `deploy-apprunner.sh` (API)
then `deploy-frontend.sh` (frontend + CloudFront + the DNS-validated
certificate for this domain). Run the API script first — the frontend script
looks up its URL automatically to wire up the `/api/*` proxy behavior.

---

## One-time setup

```bash
bash deploy-apprunner.sh    # API on App Runner
bash deploy-frontend.sh     # S3 + CloudFront + ACM cert + this domain
```

`deploy-frontend.sh` will pause partway through and print a DNS record you
need to add in GoDaddy so AWS Certificate Manager can validate you own
`lecturebot.perfectpixels.com` before it can issue the HTTPS certificate:

### GoDaddy: ACM validation record

1. Log in to [GoDaddy](https://www.godaddy.com) → **My Products** → **Domains**
2. Click **perfectpixels.com** → **DNS** (or **Manage DNS**)
3. **Add** → **CNAME**
   - **Name:** whatever the script prints (something like `_a1b2c3.lecturebot`)
   - **Value:** whatever the script prints (something like `_x9y8z7.acm-validations.aws.`)
   - **TTL:** 600 (or default)
4. Save, then let the script keep waiting (it polls automatically) — or re-run
   it later; it's idempotent and will pick up from wherever it left off.

Validation is usually fast (a few minutes) but can take up to ~30 min for DNS
to propagate.

### GoDaddy: final CNAME to CloudFront

Once the certificate is issued and the CloudFront distribution is created,
the script prints a second record — this is the one that actually makes
`lecturebot.perfectpixels.com` resolve to the app:

1. Same place: **perfectpixels.com** → **DNS** → **Add** → **CNAME**
   - **Name:** `lecturebot`
   - **Value:** the CloudFront domain the script printed (e.g. `d1234abcd.cloudfront.net`)
   - **TTL:** 600 (or default)
2. Save.

Propagation: usually 15–60 minutes, occasionally longer. The app is reachable
immediately at the raw CloudFront domain (`https://d1234abcd.cloudfront.net`)
while you wait for the custom domain to propagate.

---

## Redeploying

- **Code changes to the API**: re-run `bash deploy-apprunner.sh` — it rebuilds
  the image, pushes it, and updates the running App Runner service (including
  any changed environment variables, e.g. a rotated `CANVAS_API_TOKEN`).
- **Code changes to the frontend**: re-run `bash deploy-frontend.sh` — it
  rebuilds the static site, syncs it to S3, and invalidates the CloudFront
  cache. It detects the existing S3 bucket, certificate, and CloudFront
  distribution and reuses them rather than recreating anything.
- **Neither script needs the DNS steps repeated** once the domain is live —
  those only happen on first setup (or if the certificate/distribution were
  ever deleted).

## Troubleshooting

- **Certificate stuck at `PENDING_VALIDATION`**: double check the CNAME name —
  GoDaddy wants just the label relative to `perfectpixels.com` (the script
  already strips that), not the full record name ACM shows you elsewhere.
- **CloudFront serves a 403 for the frontend**: the S3 bucket policy scopes
  access to this specific CloudFront distribution's ARN — if you ever recreate
  the distribution without re-running the script's bucket-policy step, the old
  policy will reference a stale distribution ID.
- **`/api/*` calls fail from the deployed frontend but work locally**: check
  the App Runner service is `RUNNING` (`aws apprunner describe-service`) and
  that CloudFront's `/api/*` cache behavior is still pointed at the right
  origin domain — if the App Runner service was ever deleted and recreated,
  its URL changes and the CloudFront distribution needs updating (re-run
  `deploy-frontend.sh`, which looks up the current App Runner URL each time).
