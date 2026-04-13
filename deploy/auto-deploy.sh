#!/bin/bash
# Auto-deploy SOFIE — checks for new commits and rebuilds if found.
# Runs via cron every 5 minutes on KVM 2.
#
# Install: crontab -e
# */5 * * * * /opt/sofie/deploy/auto-deploy.sh >> /var/log/sofie-deploy.log 2>&1

set -e

REPO_DIR="/opt/sofie"
COMPOSE_FILE="docker-compose.prod.yml"
LOCK_FILE="/tmp/sofie-deploy.lock"

# Prevent concurrent deploys
if [ -f "$LOCK_FILE" ]; then
    echo "$(date): Deploy already running, skipping"
    exit 0
fi
trap "rm -f $LOCK_FILE" EXIT
touch "$LOCK_FILE"

cd "$REPO_DIR"

# Fetch latest from remote
git fetch origin main --quiet

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    exit 0
fi

echo "$(date): New commits detected ($LOCAL -> $REMOTE)"

# Pull changes
git pull origin main --quiet

# Rebuild frontend if any frontend files changed
CHANGED=$(git diff --name-only "$LOCAL" "$REMOTE")
if echo "$CHANGED" | grep -q "^frontend/"; then
    echo "$(date): Frontend changed, rebuilding..."
    cd frontend && npm install --silent && npx vite build && cd ..
fi

# Rebuild Docker if backend/Dockerfile/compose changed
if echo "$CHANGED" | grep -qE "^(backend/|Dockerfile|docker-compose|pyproject)"; then
    echo "$(date): Backend changed, rebuilding containers..."
    docker compose -f "$COMPOSE_FILE" build --quiet
    docker compose -f "$COMPOSE_FILE" up -d
else
    # Just restart to pick up any config changes
    docker compose -f "$COMPOSE_FILE" restart
fi

echo "$(date): Deploy complete ($(git rev-parse --short HEAD))"
