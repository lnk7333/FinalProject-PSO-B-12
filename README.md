# Cloud-Native Digital Guestbook (Buku Tamu Digital)

A real-time digital guestbook built with **FastAPI** and **MongoDB**, containerized with **Docker**, and deployed to **Google Cloud Run** via a DevSecOps GitHub Actions pipeline. Visitors can leave, edit, and delete messages updated live over WebSocket.

## Tech Stack

- **Backend:** Python FastAPI + WebSocket
- **Frontend:** Bootstrap 5 (static HTML served by FastAPI)
- **Database:** MongoDB (Atlas)
- **Containerization:** Docker (Python 3.11-slim)
- **CI/CD:** GitHub Actions → Trivy (security scan) → Artifact Registry → Cloud Run
- **Auth:** Workload Identity Federation (keyless GCP authentication)

## Prerequisites

- Git
- Python 3.11+
- Docker (optional — for local container testing)
- A **Google Cloud Platform** project with:
  - **Artifact Registry** repository (`pso-image-repo`) in region `asia-southeast2`
  - **Cloud Run** service (`guestbook-web`) in region `asia-southeast2`
  - **Workload Identity Federation** pool & provider configured for your GitHub repository
- A **MongoDB Atlas** cluster (or any MongoDB instance) — get your connection string

## Environment Variables

| Variable     | Description                  | Default                                        |
| ------------ | ---------------------------- | ---------------------------------------------- |
| `MONGO_URI`  | MongoDB connection string    | `mongodb://localhost:27017/guestbook_db`        |
| `PORT`       | Application listen port      | (set automatically by Cloud Run)               |

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

# 5. Run the application
uvicorn app:app --reload --host 0.0.0.0 --port 8080
```

Open `http://localhost:8080` in your browser.

## Running with Docker (Local)

```bash
# Build the image
docker build -t guestbook-web .

# Run the container
docker run -p 8080:8080 -e MONGO_URI="mongodb+srv://..." guestbook-web
```

## CI/CD Pipeline (Automated Deployment)

The pipeline is defined in `.github/workflows/deploy.yml` and triggers automatically on every push to the `main` branch.

### Pipeline Stages

1. **Checkout** — fetches the latest code
2. **GCP Authentication** — keyless login via Workload Identity Federation (no service account keys)
3. **Docker Login** — authenticates to Google Artifact Registry
4. **Build** — builds the Docker image and tags it with the commit SHA + `latest`
5. **Security Scan** — runs [Trivy](https://github.com/aquasecurity/trivy) to audit for HIGH/CRITICAL vulnerabilities; the pipeline fails if any are found
6. **Push** — pushes the verified image to Artifact Registry
7. **Deploy** — deploys the new image to Cloud Run with `--allow-unauthenticated` and `--max-instances=1`

### Required GitHub Secrets

These must be configured in your GitHub repository under **Settings → Secrets and variables → Actions**:

| Secret                           | Description                                           |
| -------------------------------- | ----------------------------------------------------- |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Workload Identity Federation provider resource name   |
| `GCP_SERVICE_ACCOUNT`            | Email of the GCP service account to impersonate       |
| `MONGO_URI`                      | MongoDB connection string (only used at deploy time)  |

The pipeline automatically resolves the GCP project ID at runtime — no manual project ID configuration needed.

## Project Structure

```
FinalProject-PSO-B-12/
├── .github/workflows/
│   └── deploy.yml          # CI/CD pipeline
├── templates/
│   └── index.html           # Frontend (Bootstrap 5)
├── app.py                   # FastAPI application
├── Dockerfile               # Container image definition
├── requirements.txt         # Python dependencies
└── README.md                # This file
```
