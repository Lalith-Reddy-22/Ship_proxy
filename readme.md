# The Ship Proxy (Single TCP)

A two-part proxy system that routes all HTTP/HTTPS traffic from a ship-side proxy over a single, persistent TCP tunnel to an offshore server, processing requests strictly in FIFO order. Works with curl and standard browser proxy settings on macOS, Linux, and Windows.

## Features
- Single long-lived TCP connection from ship to offshore.
- Sequential handling: one in-flight request at a time (request 1, then 2, then 3).
- Supports HTTP methods (GET/POST/PUT/DELETE, etc.) and HTTPS via CONNECT.
- Usable as a browser proxy and with curl on macOS/Linux/Windows.

## Repository layout


## Prerequisites
- Python 3.10+ (tested with 3.11).
- Docker and Docker Compose (optional, recommended).

## Quick start (single virtual environment)

From project root:

```bash
python3 -m venv venv
```
Activate:

Linux/macOS:

```bash
source venv/bin/activate
```

Windows PowerShell:
```bash
venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run without Docker

Open two terminals, activate the same venv in both.

Terminal 1 (offshore server):

```bash
python3 server/server.py
```

Terminal 2 (ship proxy):

```bash
python client/client.py server 9000
```

## Docker (recommended)

Build images:
```bash
docker compose build
```

Run both services:
```bash
docker compose up -d
```
Check logs:
```bash
docker compose logs -f
```

- Server listens on host port 9000, client listens on host port 8080.

## Verify
macOS/Linux:
```bash
curl -x http://localhost:8080 http://httpforever.com/
curl -x http://localhost:8080 -X POST http://httpforever.com/post -d 'a=1'
```

Windows (PowerShell/CMD):
```bash
curl.exe -x http://localhost:8080 http://httpforever.com/
```
Run the curl commands multiple times; responses should remain consistent since all requests are serialized over the single tunnel.

## Browser setup
Configure HTTP/HTTPS proxy in the browser:

- Host: localhost
- Port: 8080

HTTPS requests use CONNECT and are still processed one at a time to meet the sequential requirement.

Design notes:
- The ship proxy listens on 0.0.0.0:8080 and accepts standard HTTP proxy traffic, including CONNECT for HTTPS.

- A single persistent TCP tunnel carries requests to the offshore server using a simple length-prefixed framing protocol for headers and body.

- A lock on the ship side ensures exactly one request is processed end-to-end before the next begins (strict FIFO).# Ship_proxy
# Ship_proxy
