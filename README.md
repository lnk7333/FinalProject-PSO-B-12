# Cloud-Native Digital Guestbook (Buku Tamu Digital)

A server-rendered digital guestbook built with **Flask** and **MongoDB**, containerized with **Docker**, and deployed to **Google Cloud Run** via a DevSecOps GitHub Actions pipeline. Authenticated users can view a visit counter and leave, edit, or delete their own guestbook messages (admins have full control).

## Tech Stack

- **Backend:** Python Flask + Flask-Login
- **Frontend:** Bootstrap 5 (server-rendered Jinja2 templates)
- **Database:** MongoDB (Atlas)
- **Containerization:** Docker (Python 3.11-slim)
- **Production Server:** Gunicorn
- **Auth:** Flask-Login (session-based) + Werkzeug (PBKDF2 password hashing) + Workload Identity Federation (keyless GCP authentication for CI/CD)
- **CI/CD:** GitHub Actions → Trivy (security scan) → Artifact Registry → Cloud Run

## Prerequisites

- Git
- Python 3.11+
- Docker (optional — for local container testing)
- A **Google Cloud Platform** project with billing enabled
- A **MongoDB Atlas** cluster (or any MongoDB instance)

## Environment Variables

| Variable          | Description                           | Default                                        |
| ----------------- | ------------------------------------- | ---------------------------------------------- |
| `MONGO_URI`       | MongoDB connection string             | `mongodb://localhost:27017/guestbook_db`        |
| `PORT`            | Application listen port               | `5000` (overridden by Cloud Run at runtime)     |
| `SECRET_KEY`      | Flask session signing key             | Auto-generated (set a fixed value for production) |
| `ADMIN_USERNAME`  | Username for auto-seeded admin        | (none — no admin seeded if unset)              |
| `ADMIN_PASSWORD`  | Password for auto-seeded admin        | (none — must be set with `ADMIN_USERNAME`)     |

---

## Local Development Setup

```bash
# 1. Clone the repository
git clone <repository-url>
cd FinalProject-PSO-B-12

# 2. Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
# source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set MongoDB connection string
# Windows (PowerShell)
$env:MONGO_URI = "mongodb+srv://<username>:<password>@<cluster>.mongodb.net/guestbook_db?retryWrites=true&w=majority"
# macOS / Linux
# export MONGO_URI="mongodb+srv://..."

# 5. (Optional) Seed an admin user on first run
$env:ADMIN_USERNAME = "admin"
$env:ADMIN_PASSWORD = "admin123"

# 6. Run the application (Flask development server)
python app.py
```

Open `http://localhost:5000` in your browser (Flask default port).

### Testing the Auth System

1. Visit `http://localhost:5000` — unauthenticated users see a prompt to log in
2. Click **Register** and fill in First Name, Last Name, Nickname, and Password
   - Password must be at least 8 characters with 1 letter and 1 non-letter
3. Log in with your nickname and password
4. Post a message — the display name is auto-set from your First + Last Name
5. Edit/delete buttons only appear on your own messages
6. The admin user (if seeded) can edit/delete **all** messages

---

## Auth System

The application uses **Flask-Login** for session-based authentication and **Werkzeug** (PBKDF2+HMAC-SHA-256) for password hashing. Passwords are never stored in plaintext.

### User Schema

Each user document in MongoDB stores:

| Field           | Description                                    |
| --------------- | ---------------------------------------------- |
| `first_name`    | Display first name (shown on messages)         |
| `last_name`     | Display last name (shown on messages)          |
| `nickname`      | Unique login identifier (3-30 alphanumeric)    |
| `password_hash` | PBKDF2 hashed password                         |
| `role`          | `"user"` or `"admin"`                          |

### Access Rules

| Action                | Guest | Regular User | Admin |
| --------------------- | ----- | ------------ | ----- |
| View guestbook        | ✅    | ✅           | ✅    |
| Create entry          | ❌    | ✅           | ✅    |
| Edit own entry        | ❌    | ✅           | ✅    |
| Edit others' entry    | ❌    | ❌           | ✅    |
| Delete own entry      | ❌    | ✅           | ✅    |
| Delete others' entry  | ❌    | ❌           | ✅    |

### Registration Rules

- **First Name** — required, letters and spaces only
- **Last Name** — optional, letters and spaces only
- **Nickname** — required, 3-30 characters (letters, numbers, underscores), case-insensitive uniqueness
- **Password** — minimum 8 characters, must contain at least 1 letter and 1 non-letter (number/symbol)

### Admin Seeding

Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables to auto-create an admin account on first startup. The admin can edit and delete any guestbook entry.

---

## Running with Docker (Local)

```bash
# Build the image
docker build -t guestbook-web .

# Run the container
docker run -p 8080:8080 -e MONGO_URI="mongodb+srv://<username>:<password>@<cluster>.mongodb.net/guestbook_db?retryWrites=true&w=majority" guestbook-web
```

The container uses Gunicorn internally and binds to the port specified by the `PORT` environment variable (defaults to `8080` when not set by Cloud Run).

---

## Deploying to Google Cloud Run

Follow these steps to set up the infrastructure and deploy the application.

### Step 1: Enable Required GCP APIs

Enable the following APIs in your GCP project via the [API Library](https://console.cloud.google.com/apis/library):

- **Cloud Run API**
- **Artifact Registry API**
- **IAM Credentials API**

### Step 2: Create Artifact Registry Repository

```bash
gcloud artifacts repositories create pso-image-repo \
  --repository-format=docker \
  --location=asia-southeast2 \
  --description="Docker repository for guestbook-web images"
```

### Step 3: Configure Workload Identity Federation

Workload Identity Federation allows GitHub Actions to authenticate to GCP without storing static service account keys.

#### 3a. Create a Service Account

```bash
gcloud iam service-accounts create github-actions-deployer \
  --display-name="GitHub Actions Deployer"
```

#### 3b. Grant IAM Roles to the Service Account

```bash
# Allow pushing images to Artifact Registry
gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member="serviceAccount:github-actions-deployer@<PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# Allow deploying to Cloud Run
gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member="serviceAccount:github-actions-deployer@<PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/run.admin"

# Allow the service account to impersonate itself (required by Cloud Run)
gcloud iam service-accounts add-iam-policy-binding \
  github-actions-deployer@<PROJECT_ID>.iam.gserviceaccount.com \
  --member="serviceAccount:github-actions-deployer@<PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

#### 3c. Create a Workload Identity Pool and Provider

```bash
# Create the pool
gcloud iam workload-identity-pools create github-pool \
  --location="global" \
  --display-name="GitHub Actions Pool"

# Get the pool ID (full resource name)
gcloud iam workload-identity-pools describe github-pool \
  --location="global" \
  --format="value(name)"
```

```bash
# Create the OIDC provider for GitHub
gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"
```

#### 3d. Grant the Service Account Access to the Pool

```bash
gcloud iam service-accounts add-iam-policy-binding \
  github-actions-deployer@<PROJECT_ID>.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/github-pool/attribute.repository/<GITHUB_USER_OR_ORG>/FinalProject-PSO-B-12"
```

### Step 4: Create the Cloud Run Service

```bash
gcloud run deploy guestbook-web \
  --image=asia-southeast2-docker.pkg.dev/<PROJECT_ID>/pso-image-repo/guestbook-web:latest \
  --region=asia-southeast2 \
  --allow-unauthenticated \
  --max-instances=1
```

> **Note:** This initial deployment will fail because the image hasn't been pushed yet. That's expected — the CI/CD pipeline will push the first image and redeploy automatically.

### Step 5: Configure GitHub Secrets

In your GitHub repository, go to **Settings → Secrets and variables → Actions** and add the following secrets:

| Secret                           | Required | Value / How to Get It                                                                                      |
| -------------------------------- | :------: | ---------------------------------------------------------------------------------------------------------- |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | ✅ Yes   | Run: `gcloud iam workload-identity-pools providers describe github-provider --location=global --workload-identity-pool=github-pool --format="value(name)"` |
| `GCP_SERVICE_ACCOUNT`            | ✅ Yes   | The service account email: `github-actions-deployer@<PROJECT_ID>.iam.gserviceaccount.com`                  |
| `MONGO_URI`                      | ✅ Yes   | Your MongoDB Atlas connection string: `mongodb+srv://<username>:<password>@<cluster>.mongodb.net/guestbook_db?retryWrites=true&w=majority` |
| `SECRET_KEY`                     | ✅ Yes (recommended) | A random secret string for Flask session signing. Generate with: `python -c "import secrets; print(secrets.token_hex(32))"`. If not set, a random key is generated on each restart, logging everyone out. |
| `ADMIN_USERNAME`                 | ❌ No    | Username for the auto-seeded admin (e.g., `admin`). If not set, no admin account is created — register manually. |
| `ADMIN_PASSWORD`                 | ❌ No    | Password for the auto-seeded admin. Must be set together with `ADMIN_USERNAME`.                             |

> **⚠️ Without `MONGO_URI`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, or `GCP_SERVICE_ACCOUNT` the app will fail** at startup or during deployment. `SECRET_KEY` is strongly recommended in production to persist sessions across restarts.

### Step 6: Deploy

Push your code to the `main` branch:

```bash
git push origin main
```

The GitHub Actions pipeline will automatically:
1. Build the Docker image
2. Scan it for vulnerabilities with Trivy
3. Push the verified image to Artifact Registry
4. Deploy the new image to Cloud Run

---

## CI/CD Pipeline (Detailed)

The pipeline is defined in `.github/workflows/deploy.yml` and triggers automatically on every push to the `main` branch.

### Pipeline Stages

| Stage | Action | Description |
|-------|--------|-------------|
| 1 | **Checkout** | Fetches the latest code from the repository |
| 2 | **GCP Authentication** | Keyless login via Workload Identity Federation (no static keys) |
| 3 | **Docker Login** | Authenticates Docker to Google Artifact Registry using OAuth2 access token |
| 4 | **Build** | Builds the Docker image and tags it with the commit SHA + `latest` |
| 5 | **Security Scan** | Runs Trivy to audit for HIGH/CRITICAL vulnerabilities; pipeline fails if any are found |
| 6 | **Push** | Pushes the verified image to Artifact Registry |
| 7 | **Deploy** | Deploys the new image to Cloud Run with `--allow-unauthenticated` and `--max-instances=1` |

The pipeline resolves the GCP project ID dynamically at runtime — no manual project ID configuration is needed in the workflow file.

---

## Post-Deployment Verification

1. **Get the Cloud Run URL:**
   ```bash
   gcloud run services describe guestbook-web \
     --region=asia-southeast2 \
     --format="value(status.url)"
   ```

2. **Open the URL** in your browser. You should see the guestbook page with a visit counter and an empty list of entries (or any previously created entries).

3. **Check Cloud Run logs** for any errors:
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=guestbook-web" --limit=20
   ```

4. **Verify MongoDB connectivity** by creating a guestbook entry through the web interface. If entries appear and persist after a page refresh, the database connection is working.

---

## Project Structure

```
FinalProject-PSO-B-12/
├── .github/workflows/
│   └── deploy.yml            # CI/CD pipeline (GitHub Actions)
├── templates/
│   ├── index.html            # Guestbook page (Bootstrap 5 + Jinja2)
│   ├── login.html            # Login form
│   └── register.html         # Registration form (with live validation + password strength meter)
├── app.py                    # Flask application (routes: index, create, update, delete, login, register, logout)
├── Dockerfile                # Container image definition (Python 3.11-slim + Gunicorn)
├── FEATURES.md               # Feature specs for team implementation
├── requirements.txt          # Python dependencies
├── .gitignore                # Python + environment ignores
└── README.md                 # This file
```
