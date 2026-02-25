# Deployment Guide: Local Development to SuperNova Production

A battle-tested guide for deploying internal Amazon web applications from local development to production with SuperNova domains.

**Last Updated**: February 2026  
**Author**: Based on video-annotator deployment experience

---

## Overview

This guide covers the complete deployment journey:
1. Local development setup
2. EC2 deployment with S3 storage
3. SuperNova domain setup (internal DNS)
4. SSL certificate validation
5. Production configuration

**Time Estimate**: 2-4 hours (mostly waiting for AWS validations)

---

## Phase 1: Local Development (30 minutes)

### 1.1 Project Structure
```
project/
├── src/                    # Frontend React/TypeScript
├── server/                 # Backend Node.js/Express
├── dist/                   # Built frontend (generated)
├── package.json           # Dependencies
└── vite.config.ts         # Build configuration
```

### 1.2 Development Commands
```bash
# Install dependencies
npm install

# Run frontend dev server (port 5173)
npm run dev

# Run backend server (port 3001)
cd server && node index.js

# Build for production
npm run build
```

### 1.3 Configuration Files
Create separate configs for dev and production:

**src/config.ts** (development):
```typescript
export const API_BASE_URL = 'http://localhost:3001';
export const SOCKET_URL = API_BASE_URL;
```

**src/config.production.ts** (production):
```typescript
export const API_BASE_URL = 'http://YOUR-DOMAIN:3001';
export const SOCKET_URL = API_BASE_URL;
```

---

## Phase 2: EC2 Deployment (1 hour)

### 2.1 Launch EC2 Instance

**Via AWS Console**:
1. Go to EC2 → Launch Instance
2. Settings:
   - **AMI**: Amazon Linux 2023
   - **Instance Type**: t3.medium (or larger for production)
   - **Key Pair**: Create new or use existing (save .pem file!)
   - **Security Group**: 
     - SSH (22) from your IP
     - HTTP (80) from anywhere
     - Custom TCP (3001) from anywhere
   - **Storage**: 20GB+ (depends on video storage needs)

3. Save these values:
   - Instance ID: `i-XXXXXXXXX`
   - Public IP: `X.X.X.X`
   - Key pair location: `~/path/to/keypair.pem`

### 2.2 Install Node.js on EC2

```bash
# Connect via AWS SSM (no SSH needed)
aws ssm start-session --target i-XXXXXXXXX

# Or via SSH
ssh -i ~/path/to/keypair.pem ec2-user@X.X.X.X

# Install Node.js 20.x
curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
sudo yum install -y nodejs

# Verify
node --version
npm --version
```

### 2.3 Deploy Application

**From your local machine**:
```bash
# Build frontend
npm run build

# Copy frontend to EC2
scp -i ~/path/to/keypair.pem -r dist/* ec2-user@X.X.X.X:/home/ec2-user/dist/

# Copy server files
scp -i ~/path/to/keypair.pem -r server/* ec2-user@X.X.X.X:/home/ec2-user/server/

# Copy package files
scp -i ~/path/to/keypair.pem package*.json ec2-user@X.X.X.X:/home/ec2-user/
```

**On EC2**:
```bash
# Install dependencies
cd /home/ec2-user
npm install --production

# Start server (background process)
# IMPORTANT: Run from server directory so .env file is loaded
cd /home/ec2-user/server
NODE_ENV=production node index.js > ../server.log 2>&1 &

# Verify it's running
curl http://localhost:3001/api/health
# Should show: "storage":"s3" if S3 is configured
```

### 2.4 Test with IP Address

Visit: `http://X.X.X.X:3001`

If it works, you're ready for Phase 3!

---

## Phase 3: S3 Storage Setup (30 minutes)

### 3.1 Create S3 Bucket

```bash
# Create bucket
aws s3 mb s3://your-video-bucket-name --region us-east-1

# Enable versioning (optional but recommended)
aws s3api put-bucket-versioning \
  --bucket your-video-bucket-name \
  --versioning-configuration Status=Enabled
```

### 3.2 Configure CORS

Create `cors-config.json`:
```json
{
  "CORSRules": [
    {
      "AllowedOrigins": ["*"],
      "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
      "AllowedHeaders": ["*"],
      "ExposeHeaders": ["ETag"],
      "MaxAgeSeconds": 3000
    }
  ]
}
```

Apply CORS:
```bash
aws s3api put-bucket-cors \
  --bucket your-video-bucket-name \
  --cors-configuration file://cors-config.json
```

### 3.3 Create IAM Role for EC2

**Via AWS Console**:
1. IAM → Roles → Create Role
2. Trusted entity: AWS service → EC2
3. Permissions: `AmazonS3FullAccess` (or create custom policy)
4. Name: `EC2-S3-Access-Role`
5. Attach to EC2 instance: EC2 → Instance → Actions → Security → Modify IAM role

### 3.4 Update Server Environment

**On EC2**, create `.env` file in the server directory:
```bash
cat > /home/ec2-user/server/.env <<EOF
AWS_S3_BUCKET=your-video-bucket-name
AWS_REGION=us-east-1
PORT=3001
NODE_ENV=production
EOF
```

Restart server:
```bash
sudo pkill -9 node
cd /home/ec2-user/server
NODE_ENV=production node index.js > ../server.log 2>&1 &
```

Verify S3 is working:
```bash
curl http://localhost:3001/api/health
# Should show: "storage":"s3"
```

---

## Phase 4: SuperNova Domain Setup (2-3 hours)

### 4.1 Create Bindle (Software Registration)

**IMPORTANT**: SuperNova requires a Bindle ID for ownership tracking.

1. Go to: https://bindles.amazon.com/v2/software_app/new
2. Fill in:
   - **Name**: Your App Name
   - **Description**: Brief description
   - **Purpose**: Internal tool for [use case]
3. **Save the Bindle ID**: `amzn1.bindle.resource.XXXXXXXXXX`

### 4.2 Create IAM Role for SuperNova

```bash
# Create trust policy
cat > /tmp/supernova-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "supernova.amazon.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name Nova-DO-NOT-DELETE \
  --assume-role-policy-document file:///tmp/supernova-trust-policy.json \
  --description "SuperNova Route53 Access Role"

# Attach Route53 policy
aws iam attach-role-policy \
  --role-name Nova-DO-NOT-DELETE \
  --policy-arn arn:aws:iam::aws:policy/AmazonRoute53FullAccess

# Get the ARN (save this!)
aws iam get-role --role-name Nova-DO-NOT-DELETE --query 'Role.Arn' --output text
```

**Save**: `arn:aws:iam::XXXXXXXXXXXX:role/Nova-DO-NOT-DELETE`

### 4.3 Request SuperNova Domain

**CRITICAL LESSONS LEARNED**:
- ❌ SuperNova does NOT support `.aws.amazon.com` domains
- ✅ SuperNova ONLY supports `.aws.dev` and `.amazon.dev`
- ✅ Use "people" organization for personal/testing domains
- ❌ CDO organization requires production Isengard accounts
- ❌ AWS organization requires production Isengard accounts

**Recommended Approach**:

1. Go to: https://supernova.amazon.dev
2. Click "Request Domain"
3. Fill in:
   - **Are you in AWS or CDO?**: CDO
   - **Organization**: `people` (for personal domains)
   - **Sub-domain**: `your-app-name`
   - **Bindle ID**: `amzn1.bindle.resource.XXXXXXXXXX`
   - **IAM Role ARN**: `arn:aws:iam::XXXXXXXXXXXX:role/Nova-DO-NOT-DELETE`
   - **AWS Account ID**: `XXXXXXXXXXXX` (12 digits only, no ARN!)

4. Result: `your-app-name.YOUR-USERNAME.people.aws.dev`

**Common Errors**:
- "Invalid Production Isengard account" → Use "people" organization
- "Domain name validation failed" → Must end in `.aws.dev` or `.amazon.dev`
- "IAM Role ARN validation failed" → Don't mix account ID with ARN in form fields

### 4.4 Wait for SuperNova Delegation

SuperNova will:
1. Create Route53 hosted zone (usually instant)
2. Delegate DNS from parent domain (can take minutes to hours)
3. Show status as "Active" when ready

Check status:
```bash
# List hosted zones
aws route53 list-hosted-zones --query 'HostedZones[].{Name: Name, Id: Id}' --output table

# You should see: your-username.people.aws.dev
```

---

## Phase 5: SSL Certificate (30 minutes)

### 5.1 Request Certificate

```bash
DOMAIN="your-app-name.your-username.people.aws.dev"

# Request certificate
CERT_ARN=$(aws acm request-certificate \
  --domain-name "$DOMAIN" \
  --validation-method DNS \
  --region us-east-1 \
  --query 'CertificateArn' \
  --output text)

echo "Certificate ARN: $CERT_ARN"
```

### 5.2 Get Validation CNAME

```bash
# Wait 5 seconds for AWS to generate validation record
sleep 5

# Get validation CNAME
aws acm describe-certificate \
  --certificate-arn "$CERT_ARN" \
  --region us-east-1 \
  --query 'Certificate.DomainValidationOptions[0].ResourceRecord' \
  --output json | jq
```

Output will look like:
```json
{
  "Name": "_XXXXXXXX.your-app-name.your-username.people.aws.dev.",
  "Type": "CNAME",
  "Value": "_YYYYYYYY.jkddzztszm.acm-validations.aws."
}
```

### 5.3 Add Validation CNAME to Route53

```bash
# Get hosted zone ID
HOSTED_ZONE_ID=$(aws route53 list-hosted-zones \
  --query "HostedZones[?Name=='your-username.people.aws.dev.'].Id" \
  --output text | cut -d'/' -f3)

# Get validation record details
VALIDATION=$(aws acm describe-certificate \
  --certificate-arn "$CERT_ARN" \
  --region us-east-1 \
  --query 'Certificate.DomainValidationOptions[0].ResourceRecord' \
  --output json)

CNAME_NAME=$(echo "$VALIDATION" | jq -r '.Name')
CNAME_VALUE=$(echo "$VALIDATION" | jq -r '.Value')

# Create change batch
cat > /tmp/validation-cname.json <<EOF
{
  "Changes": [
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "$CNAME_NAME",
        "Type": "CNAME",
        "TTL": 300,
        "ResourceRecords": [
          {
            "Value": "$CNAME_VALUE"
          }
        ]
      }
    }
  ]
}
EOF

# Add to Route53
aws route53 change-resource-record-sets \
  --hosted-zone-id "$HOSTED_ZONE_ID" \
  --change-batch file:///tmp/validation-cname.json
```

### 5.4 Wait for Validation

```bash
# Check certificate status (repeat every minute)
aws acm describe-certificate \
  --certificate-arn "$CERT_ARN" \
  --region us-east-1 \
  --query 'Certificate.Status' \
  --output text

# When it shows "ISSUED", you're ready!
```

**Typical wait time**: 5-10 minutes

---

## Phase 6: Point Domain to EC2 (5 minutes)

### 6.1 Create A Record

```bash
DOMAIN="your-app-name.your-username.people.aws.dev"
EC2_IP="X.X.X.X"
HOSTED_ZONE_ID="Z0XXXXXXXXXX"  # From Phase 5.3

# Create A record
cat > /tmp/create-a-record.json <<EOF
{
  "Changes": [
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "$DOMAIN",
        "Type": "A",
        "TTL": 300,
        "ResourceRecords": [
          {
            "Value": "$EC2_IP"
          }
        ]
      }
    }
  ]
}
EOF

# Add to Route53
aws route53 change-resource-record-sets \
  --hosted-zone-id "$HOSTED_ZONE_ID" \
  --change-batch file:///tmp/create-a-record.json
```

### 6.2 Test DNS Resolution

```bash
# Test DNS
dig +short your-app-name.your-username.people.aws.dev A

# Should return: X.X.X.X (your EC2 IP)
```

---

## Phase 7: Nginx Reverse Proxy and HTTPS Setup (30 minutes)

### 7.1 Why Nginx and HTTPS?

**CRITICAL**: `.aws.dev` domains are on the HSTS preload list, which means browsers FORCE HTTPS. You cannot use HTTP with `.aws.dev` domains.

Benefits:
- Port-free access: `https://your-domain` instead of `http://your-domain:3001`
- Automatic HTTPS enforcement
- Free SSL certificates with Let's Encrypt
- Static file serving for better performance

### 7.2 Fix Security Group Rules

**CRITICAL**: EC2 instances need egress rules to download packages.

**From your local machine** (with fresh Isengard credentials):
```bash
# Add egress rule to allow all outbound traffic
aws ec2 authorize-security-group-egress \
  --group-id sg-XXXXXXXXX \
  --protocol all \
  --cidr 0.0.0.0/0

# Open port 443 for HTTPS
aws ec2 authorize-security-group-ingress \
  --group-id sg-XXXXXXXXX \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0
```

If you get "InvalidPermission.Duplicate" error, the rule already exists (that's good!).

### 7.3 Install Nginx

**SSH to EC2**:
```bash
ssh -i ~/path/to/keypair.pem ec2-user@X.X.X.X
```

**Install nginx**:
```bash
# Install nginx
sudo yum install -y nginx

# Verify installation
nginx -v

# Create config directory if needed
sudo mkdir -p /etc/nginx/conf.d
```

### 7.4 Install Certbot and Get SSL Certificate

**IMPORTANT**: Use Let's Encrypt (free) instead of AWS ACM for EC2 deployments.

```bash
# Install certbot
sudo python3 -m ensurepip --upgrade
sudo pip3 install certbot certbot-nginx

# Get SSL certificate (certbot auto-configures nginx)
sudo certbot --nginx \
  -d your-app-name.your-username.people.aws.dev \
  --non-interactive \
  --agree-tos \
  --email your-email@amazon.com \
  --redirect
```

Certbot will:
- Get a free SSL certificate from Let's Encrypt
- Automatically configure nginx for HTTPS
- Set up HTTP → HTTPS redirect
- Configure certificate auto-renewal

**Verify certificate**:
```bash
# Check certificate status
sudo certbot certificates

# Test HTTPS
curl -I https://your-app-name.your-username.people.aws.dev

# Check nginx is listening on 443
sudo netstat -tlnp | grep :443
```

### 7.5 Update Nginx Config for Static Files

Certbot creates a basic config, but we need to optimize it for static file serving:

```bash
# View the certbot-generated config
sudo cat /etc/nginx/conf.d/video-annotator.conf

# Update it to serve static files directly
sudo tee /etc/nginx/conf.d/video-annotator.conf > /dev/null <<'EOF'
server {
    listen 80;
    server_name your-app-name.your-username.people.aws.dev;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name your-app-name.your-username.people.aws.dev;

    ssl_certificate /etc/letsencrypt/live/your-app-name.your-username.people.aws.dev/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-app-name.your-username.people.aws.dev/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Serve static files directly
    location /assets/ {
        alias /home/ec2-user/dist/assets/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /vite.svg {
        alias /home/ec2-user/dist/vite.svg;
    }

    # Proxy API requests
    location /api/ {
        proxy_pass http://localhost:3001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Proxy Socket.io
    location /socket.io/ {
        proxy_pass http://localhost:3001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Serve index.html for root and SPA routes
    location / {
        root /home/ec2-user/dist;
        try_files $uri $uri/ /index.html;
    }
}
EOF

# Test config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### 7.6 Update Application Config

Edit `src/config.production.ts`:
```typescript
export const API_BASE_URL = 'https://your-app-name.your-username.people.aws.dev';
export const SOCKET_URL = API_BASE_URL;
```

**IMPORTANT**: Use HTTPS, not HTTP. The domain will force HTTPS anyway.

### 7.7 Rebuild and Deploy

```bash
# Build
npm run build

# Deploy to EC2
scp -i ~/path/to/keypair.pem -r dist/* ec2-user@X.X.X.X:/home/ec2-user/dist/
```

### 7.8 Test Production

**Primary URL**: `https://your-app-name.your-username.people.aws.dev`  
**Fallback**: `http://X.X.X.X:3001` (for troubleshooting)

**Note**: The domain will automatically redirect HTTP to HTTPS.

---

## Phase 8: Network Access and Troubleshooting

### 8.1 Understanding `.aws.dev` Domain Requirements

**CRITICAL**: `.aws.dev` domains are on the HSTS preload list:
- Browsers FORCE HTTPS (cannot use HTTP)
- Typing `http://` gets auto-upgraded to `https://`
- HTTPS setup is REQUIRED, not optional

### 8.2 Video Visibility

Videos are stored in two places:
1. **Video files**: S3 bucket (accessible from anywhere with pre-signed URLs)
2. **Video metadata**: Local JSON file on EC2 (`server/data/videos.json`)

All users accessing the same EC2 instance will see the same videos, regardless of network location.

### 8.3 Testing Access

**From external location**:
```bash
# Test HTTPS
curl -I https://your-app-name.your-username.people.aws.dev

# Should return: HTTP/1.1 200 OK
```

**From browser**:
- Always use: `https://your-app-name.your-username.people.aws.dev`
- Browser will auto-upgrade HTTP to HTTPS
- Videos should load from S3

---

## Troubleshooting

### HTTPS Required for .aws.dev Domains

**Symptoms**: Browser changes `http://` to `https://` automatically, site won't load

**Cause**: `.aws.dev` domains are on HSTS preload list - browsers force HTTPS

**Solution**: Must set up HTTPS with Let's Encrypt (see Phase 7)

### Nginx Connection Refused Errors

**Symptoms**: Nginx logs show "connect() failed (111: Connection refused)"

**Causes**:
1. Node.js server not running
2. Server crashed after nginx was started
3. Server running but not listening on port 3001

**Solutions**:
```bash
# SSH to EC2
ssh -i ~/path/to/keypair.pem ec2-user@X.X.X.X

# Check if node is running
ps aux | grep node

# Restart server
sudo pkill -9 node
sleep 2
cd /home/ec2-user/server
NODE_ENV=production node index.js > ../server.log 2>&1 &

# Test both endpoints
curl http://localhost:3001/api/health
curl https://localhost/api/health
```

### Security Group Egress Rules Missing

**Symptoms**: `yum install` times out with "Connection timed out" errors

**Cause**: Security group has no egress rules (outbound traffic blocked)

**Solution**:
```bash
aws ec2 authorize-security-group-egress \
  --group-id sg-XXXXXXXXX \
  --protocol all \
  --cidr 0.0.0.0/0
```

### Videos Not Loading from External Access

**Symptoms**: 
- Page loads but no videos appear
- Works from one location but not another
- Browser console shows API errors

**Causes**:
1. Frontend config pointing to wrong URL (HTTP vs HTTPS)
2. CORS issues with mixed content
3. API calls failing due to protocol mismatch

**Solution**: Ensure `src/config.production.ts` uses HTTPS:
```typescript
export const API_BASE_URL = 'https://your-app-name.your-username.people.aws.dev';
export const SOCKET_URL = API_BASE_URL;
```

Then rebuild and redeploy:
```bash
npm run build
scp -i ~/path/to/keypair.pem -r dist/* ec2-user@X.X.X.X:/home/ec2-user/dist/
```

### Domain Works Externally But Not Internally

**Symptoms**: 
- `curl` from external server works
- Browser from Amazon network hangs or times out
- IP address works, domain doesn't

**Cause**: `.people.aws.dev` domains may require VPN for internal access

**Solutions**:
1. Connect to Amazon VPN
2. Use IP address: `http://X.X.X.X:3001`
3. Test from external network (phone, home)

### Certificate Stuck in "Pending Validation"

**Symptoms**: Certificate shows PENDING_VALIDATION for hours

**Causes**:
1. CNAME record not added to Route53
2. Wrong hosted zone (subdomain vs parent zone)
3. DNS not propagated yet

**Solutions**:
```bash
# Verify CNAME exists
aws route53 list-resource-record-sets \
  --hosted-zone-id "$HOSTED_ZONE_ID" \
  --query "ResourceRecordSets[?Type=='CNAME']" \
  --output json | jq

# Test DNS resolution
dig +short _XXXXXXXX.your-domain.aws.dev CNAME

# If empty, CNAME wasn't added or DNS hasn't propagated
```

### SuperNova Domain Request Fails

**Error**: "Only Production Isengard accounts allowed"

**Solution**: Use "people" organization instead of AWS/CDO

**Error**: "Domain name validation failed"

**Solution**: Ensure domain ends in `.aws.dev` or `.amazon.dev`

### EC2 Server Not Responding

```bash
# Check if server is running
aws ssm send-command \
  --instance-ids i-XXXXXXXXX \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["ps aux | grep node"]'

# Check server logs
aws ssm send-command \
  --instance-ids i-XXXXXXXXX \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["tail -50 /home/ec2-user/server.log"]'

# Restart server (CRITICAL: run from server directory)
aws ssm send-command \
  --instance-ids i-XXXXXXXXX \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo pkill -9 node","sleep 2","cd /home/ec2-user/server && NODE_ENV=production node index.js > ../server.log 2>&1 &"]'
```

**Common Issues**:
- Port 3001 already in use: Use `sudo pkill -9 node` to kill all node processes
- Server shows "storage":"local" instead of "s3": Must run from `/home/ec2-user/server` directory so `.env` file is loaded
- S3 videos return 403: Check EC2 IAM role has S3 permissions and public access block settings

### S3 Videos Return 403 Errors

**Symptoms**: Videos show "Video Failed to Load" with 403 errors in console

**Causes**:
1. S3 public access block preventing pre-signed URLs
2. EC2 IAM role missing S3 permissions
3. Server not running from correct directory (using local storage instead of S3)

**Solutions**:
```bash
# 1. Check S3 public access block
aws s3api get-public-access-block --bucket your-video-bucket-name

# 2. Allow pre-signed URLs (keep public access blocked)
aws s3api put-public-access-block \
  --bucket your-video-bucket-name \
  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=false,RestrictPublicBuckets=false"

# 3. Verify EC2 IAM role has S3 permissions
aws iam list-attached-role-policies --role-name VideoAnnotatorRole

# 4. Ensure server is using S3 (not local storage)
curl http://3.81.247.175:3001/api/health
# Should show: "storage":"s3"

# If showing "local", restart from server directory:
# SSH to EC2:
sudo pkill -9 node
cd /home/ec2-user/server
NODE_ENV=production node index.js > ../server.log 2>&1 &
```

**Issue**: Isengard credentials expire after 1 hour

**Solution**: Refresh credentials frequently
```bash
# Get new credentials from Isengard
# https://isengard.amazon.com
# Select account → Credentials → bash/zsh tab
# Copy and paste export commands
```

---

## Production Checklist

Before going live:

- [ ] EC2 instance running and accessible
- [ ] S3 bucket created with CORS configured
- [ ] IAM role attached to EC2 for S3 access
- [ ] Bindle created and ID saved
- [ ] SuperNova IAM role created
- [ ] SuperNova domain requested and active
- [ ] SSL certificate issued (ISSUED status)
- [ ] DNS A record pointing to EC2
- [ ] Application config updated with domain
- [ ] Frontend rebuilt and deployed
- [ ] Server restarted with production config
- [ ] Health check endpoint responding
- [ ] Test upload and playback working

---

## Key Takeaways

### What Worked
✅ Using "people" organization for personal domains  
✅ Creating parent zone (username.people.aws.dev) instead of subdomain zone  
✅ Adding validation CNAME to parent zone  
✅ Using AWS SSM for EC2 access (no SSH needed)  
✅ Separate config files for dev/production  
✅ Running server from `/home/ec2-user/server` directory to load `.env` properly  
✅ Using `sudo pkill -9 node` to kill stuck processes  
✅ Setting S3 public access block to allow pre-signed URLs while blocking public access  
✅ Let's Encrypt with certbot for free SSL certificates  
✅ Nginx reverse proxy with static file serving  
✅ HTTPS configuration (required for .aws.dev domains)  
✅ Adding security group egress rules for package installation  

### What Didn't Work
❌ Trying to use `.aws.amazon.com` domains (not supported)  
❌ Using CDO/AWS organizations without production accounts  
❌ Creating separate hosted zones for subdomains  
❌ Mixing AWS Account ID with IAM Role ARN in forms  
❌ Using HTTP with `.aws.dev` domains (HSTS forces HTTPS)  
❌ AWS ACM certificates for EC2 (use Let's Encrypt instead)  

### Critical Lessons
- **`.aws.dev` domains REQUIRE HTTPS** - browsers force it via HSTS preload
- Let's Encrypt is easier than AWS ACM for EC2 deployments
- Certbot auto-configures nginx and handles renewals
- Frontend config must match protocol (HTTPS not HTTP)
- Security group needs both ingress (80, 443, 3001) and egress rules
- Nginx should serve static files directly, proxy API/Socket.io only

### Time Savers
- Use certbot with `--nginx` flag for automatic configuration
- Let certbot handle HTTP → HTTPS redirects
- Test with `curl` from EC2 before testing in browser
- Keep Isengard credentials fresh (refresh every 30 minutes)
- Use IP address for troubleshooting when domain has issues

---

## Resources

- **SuperNova Portal**: https://supernova.amazon.dev
- **Bindles**: https://bindles.amazon.com
- **AWS Certificate Manager**: https://console.aws.amazon.com/acm
- **Route53**: https://console.aws.amazon.com/route53
- **Isengard**: https://isengard.amazon.com

---

## Example: Complete Deployment

**Project**: Video Annotator  
**Domain**: `video-annotator.jllevine.people.aws.dev`  
**EC2 IP**: `3.81.247.175`  
**Instance**: `i-0af89297af85fcb5b`  
**Account**: `427791004700`  
**Region**: `us-east-1`  

**Timeline**:
- Phase 1 (Local): 30 minutes
- Phase 2 (EC2): 1 hour
- Phase 3 (S3): 30 minutes
- Phase 4 (SuperNova): 2 hours (mostly waiting)
- Phase 5 (Certificate): Not needed with Let's Encrypt
- Phase 6 (DNS): 5 minutes
- Phase 7 (Nginx + HTTPS): 30 minutes
- Phase 8 (Testing): 10 minutes

**Total**: ~4.5 hours (including wait times)

**Note**: Using Let's Encrypt eliminates the ACM certificate wait time from Phase 5.

---

**Document Version**: 1.0  
**Last Tested**: February 2026  
**Success Rate**: 100% when following "people" organization path
