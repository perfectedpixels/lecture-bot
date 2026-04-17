# Lecture-Bot Subdomain on perfectpixels.com (GoDaddy)

Two ways to make lecture-bot available at a subdomain like `lecturebot.perfectpixels.com`:

---

## Option A: Domain Redirect (Simplest — Stay on Streamlit Cloud)

**Result:** Users visit `lecturebot.perfectpixels.com` and are redirected to `lecture-bot.streamlit.app`. The URL bar will show the Streamlit URL after redirect.

### GoDaddy Setup

1. Log in to [GoDaddy](https://www.godaddy.com) → **My Products** → **Domains**
2. Click **perfectpixels.com** → **DNS** or **Manage DNS**
3. Add a **Forwarding** record (not a CNAME):
   - **Type:** Domain Forwarding (or "Forwarding" in the DNS/Forwarding section)
   - **Subdomain:** `lecturebot` (or `lecture-bot` — use one without special chars)
   - **Forward to:** `https://lecture-bot.streamlit.app`
   - **Redirect type:** 301 (permanent) or 302 (temporary)
   - **Settings:** Forward only (not masking — masking can break Streamlit)

**Alternative path:** GoDaddy sometimes puts this under **Domain** → **Forwarding** → **Add Forwarding** → choose subdomain.

### Notes

- Propagation: usually 15–60 minutes, up to 48 hours
- SSL: GoDaddy handles HTTPS for the redirect
- The final URL will be `lecture-bot.streamlit.app`; the custom domain is only used for the initial visit

---

## Option B: True Custom Domain (Requires Different Hosting)

**Result:** `lecturebot.perfectpixels.com` serves the app directly; the URL stays as your domain.

Streamlit Community Cloud does **not** support custom domains. You need a host that does (e.g. Railway, Render, Fly.io).

### Using Railway

1. **Deploy to Railway**
   - Connect your GitHub repo
   - Add a new service from the `lecture-bot` repo
   - Set build command: `pip install -r requirements.txt`
   - Set start command: `streamlit run app/streamlit_app_redesign.py --server.port $PORT --server.address 0.0.0.0`
   - Add env vars (AWS keys, `BEDROCK_KNOWLEDGE_BASE_ID`, etc.)

2. **Add custom domain in Railway**
   - Service → **Settings** → **Networking** → **Custom Domain**
   - Add: `lecturebot.perfectpixels.com`
   - Railway will show a CNAME target (e.g. `xxx.up.railway.app`)

3. **GoDaddy DNS**
   - **Type:** CNAME
   - **Name:** `lecturebot` (or `@` if using a different subdomain setup)
   - **Value:** the Railway CNAME target (e.g. `your-app.up.railway.app`)
   - **TTL:** 600 or default

4. **SSL**
   - Railway provisions SSL via Let's Encrypt for your custom domain

### GoDaddy CNAME Steps (for Option B)

1. **My Products** → **Domains** → **perfectpixels.com** → **DNS**
2. **Add** → **CNAME**
3. **Name:** `lecturebot` (creates `lecturebot.perfectpixels.com`)
4. **Value:** your host’s CNAME target (e.g. `xyz.up.railway.app`)
5. **TTL:** 600 (10 min) or 1 hour
6. Save

---

## Subdomain Name Options

| Subdomain        | URL                         | Notes                    |
|------------------|-----------------------------|--------------------------|
| `lecturebot`     | lecturebot.perfectpixels.com | No hyphen                |
| `lecture-bot`    | lecture-bot.perfectpixels.com | Some DNS allow hyphens  |
| `lecture`        | lecture.perfectpixels.com   | Short                    |

---

## Quick Reference: Option A (Redirect)

```
GoDaddy → Domain → perfectpixels.com → Forwarding
Add: lecturebot.perfectpixels.com → https://lecture-bot.streamlit.app
```

## Quick Reference: Option B (CNAME)

```
1. Deploy app to Railway (or Render/Fly.io)
2. Add custom domain in host: lecturebot.perfectpixels.com
3. GoDaddy DNS: CNAME lecturebot → [host CNAME target]
```
