# Docker implementation (Service A)

This guide explains how to **build**, **push** to Docker Hub, **pull**, and **run** **Service A (Web UI)**.

Service A runs:

```bash
uvicorn app:app --reload --port 8000
```

---

## 1) Prerequisites

- Docker Desktop installed and running
- A Docker Hub account (username like `mydockeruser`)

Optional but recommended:
- A `.env` file for runtime configuration (API keys, service URLs, etc.)

---

## 2) Build the image locally

From the repo root (same folder as `Dockerfile`):

```bash
docker build -t <dockerhub_username>/badger-service-a:latest .
```

Example:

```bash
docker build -t mydockeruser/badger-service-a:latest .
```

Notes:
- The image installs dependencies from `requirements.docker.txt` (Linux-friendly; excludes Windows-only UI automation packages).

---

## 3) Push the image to Docker Hub

Login:

```bash
docker login
```

Push:

```bash
docker push <dockerhub_username>/badger-service-a:latest
```

Example:

```bash
docker push mydockeruser/badger-service-a:latest
```

---

## 4) Pull on the client machine

On the client machine:

```bash
docker pull <dockerhub_username>/badger-service-a:latest
```

Example:

```bash
docker pull mydockeruser/badger-service-a:latest
```

---

## 5) Run on the client machine

### Option A (recommended): run with an env file + persistent outputs

1) Create a folder for the container data (example: `C:\badger-service-a`).
2) Put a `.env` file inside it (example: `C:\badger-service-a\.env`).
3) Run:

```bash
docker run --rm -it ^
  -p 8000:8000 ^
  --env-file "C:\badger-service-a\.env" ^
  -v "C:\badger-service-a\outputs:/app/outputs" ^
  <dockerhub_username>/badger-service-a:latest
```

Then open:
- `http://localhost:8000`

Notes:
- The `-v ...:/app/outputs` mapping keeps generated files even if the container is removed.

### Option B: run without an env file

```bash
docker run --rm -it -p 8000:8000 <dockerhub_username>/badger-service-a:latest
```

---

## 6) Common useful commands

List running containers:

```bash
docker ps
```

Stop a running container:

```bash
docker stop <container_id>
```

See logs:

```bash
docker logs -f <container_id>
```

