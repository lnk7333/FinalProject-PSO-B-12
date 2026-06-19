# FinalProject-PSO-B-12 — Feature Overview

## Core Features

### Guestbook CRUD
- View, create, edit, and delete guestbook entries
- Edit/delete restricted to the message owner or an admin
- Visit counter increments on every page load

### User Authentication (Flask-Login)
- **Register** — first name, last name, nickname, password with live validation and strength meter
- **Login / Logout** — session-based auth via `__session` cookie (Firebase Hosting compatible)
- **Password security** — PBKDF2+HMAC-SHA-256 hashing, minimum 8 chars with letter + non-letter requirement

### Role-Based Access
- **User** — create, edit, and delete own messages
- **Admin** — full control over all messages, plus admin dashboard

## Additional Features

### Profile Settings (`/profile`)
Logged-in users can update their first name, last name, or change password (requires current password verification).

### Admin Dashboard (`/admin`)
Admin-only page displaying:
- System stats (total users, entries, visits)
- User list with message counts and role management (promote/demote)

### Reactions / Likes (`/like/<id>`)
Logged-in users can like or unlike any guestbook entry. Each entry shows a live like count. Toggle state is persisted per user.

## Deployment & Infrastructure

- **Containerized** with Docker (Python 3.11-slim + Gunicorn)
- **CI/CD** via GitHub Actions — automatic build, Trivy security scan, push to Artifact Registry, deploy to Cloud Run
- **Custom domain** (`digital-guestbook.my.id`) proxied through Firebase Hosting
- **Session cookie** named `__session` with `Cache-Control: private` for Firebase CDN compatibility
