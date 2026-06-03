# Cloud-Native Digital Guestbook (Buku Tamu Digital)

A server-rendered digital guestbook built with **Flask** and **MongoDB**, containerized with **Docker**, and deployed to **Google Cloud Run** via a DevSecOps GitHub Actions pipeline. Visitors can view a visit counter and leave, edit, or delete guestbook messages.

## Tech Stack

- **Backend:** Python Flask
- **Frontend:** Bootstrap 5 (server-rendered Jinja2 templates)
- **Database:** MongoDB (Atlas)
- **Containerization:** Docker (Python 3.11-slim)
- **Production Server:** Gunicorn
- **CI/CD:** GitHub Actions → Trivy (security scan) → Artifact Registry → Cloud Run
- **Auth:** Workload Identity Federation (keyless GCP authentication)

## Prerequisites

- Git
- Python 3.11+
- Docker (optional — for local container testing)
- A **Google Cloud Platform** project with billing enabled
- A **MongoDB Atlas** cluster (or any MongoDB instance)

## Environment Variables

| Variable     | Description                  | Default                                        |
| ------------ | ---------------------------- | ---------------------------------------------- |
| `MONGO_URI`  | MongoDB connection string    | `mongodb://localhost:27017/guestbook_db`        |
| `PORT`       | Application listen port      | `5000` (overridden by Cloud Run at runtime)     |

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

# 5. Run the application (Flask development server)
python app.py
```

Open `http://localhost:5000` in your browser (Flask default port).

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

| Secret                           | Value / How to Get It                                                                                      |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Run: `gcloud iam workload-identity-pools providers describe github-provider --location=global --workload-identity-pool=github-pool --format="value(name)"` |
| `GCP_SERVICE_ACCOUNT`            | The service account email: `github-actions-deployer@<PROJECT_ID>.iam.gserviceaccount.com`                  |
| `MONGO_URI`                      | Your MongoDB Atlas connection string: `mongodb+srv://<username>:<password>@<cluster>.mongodb.net/guestbook_db?retryWrites=true&w=majority` |

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
│   └── deploy.yml          # CI/CD pipeline (GitHub Actions)
├── templates/
│   └── index.html           # Frontend template (Bootstrap 5 + Jinja2)
├── app.py                   # Flask application (routes: index, create, update, delete)
├── Dockerfile               # Container image definition (Python 3.11-slim + Gunicorn)
├── requirements.txt         # Python dependencies
└── README.md                # This file
```
