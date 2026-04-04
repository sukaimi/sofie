#!/bin/bash
# SOFIE Deployment Script for Vast.ai / RunPod GPU instances
# Usage: ssh into the GPU instance, then run this script.
#
# Prerequisites:
# - Docker and Docker Compose installed (most GPU instances have these)
# - NVIDIA drivers + nvidia-container-toolkit (standard on GPU instances)
# - Git installed

set -e

echo "========================================="
echo "  SOFIE Deployment"
echo "========================================="
echo ""

# 1. Clone repo (or pull if already cloned)
if [ -d "sofie" ]; then
    echo "[1/6] Updating existing repo..."
    cd sofie
    git pull origin main
else
    echo "[1/6] Cloning repo..."
    git clone https://github.com/sukaimi/sofie.git
    cd sofie
fi

# 2. Create .env if not exists
if [ ! -f ".env" ]; then
    echo "[2/6] Creating .env from template..."
    cp .env.example .env
    echo ""
    echo "  !! IMPORTANT: Edit .env to set your API keys !!"
    echo "  Run: nano .env"
    echo "  Then re-run this script."
    echo ""
    echo "  Key settings to change:"
    echo "    COMFYUI_MOCK=false"
    echo "    LLM_MODEL=gemma4:26b-a4b   (or your preferred model)"
    echo "    VISION_MODEL=gemma4:26b-a4b"
    echo "    FLUX_API_KEY=your-key       (if using OpenRouter for image gen)"
    echo "    FLUX_API_PROVIDER=openrouter"
    echo ""
    exit 0
else
    echo "[2/6] .env exists, using existing configuration."
fi

# 3. Start the stack
echo "[3/6] Starting Docker Compose stack..."
docker compose up -d --build

# 4. Wait for Ollama to be ready
echo "[4/6] Waiting for Ollama to start..."
sleep 10
until docker exec sofie-ollama-1 ollama list 2>/dev/null; do
    echo "  Waiting for Ollama..."
    sleep 5
done

# 5. Pull LLM model
LLM_MODEL=$(grep LLM_MODEL .env | cut -d= -f2 | tr -d '"' | tr -d "'")
LLM_MODEL=${LLM_MODEL:-gemma4:26b-a4b}
echo "[5/6] Pulling LLM model: $LLM_MODEL"
docker exec sofie-ollama-1 ollama pull "$LLM_MODEL"

# Check if vision model is different from LLM model
VISION_MODEL=$(grep VISION_MODEL .env | cut -d= -f2 | tr -d '"' | tr -d "'")
VISION_MODEL=${VISION_MODEL:-$LLM_MODEL}
if [ "$VISION_MODEL" != "$LLM_MODEL" ]; then
    echo "  Also pulling vision model: $VISION_MODEL"
    docker exec sofie-ollama-1 ollama pull "$VISION_MODEL"
fi

# 6. Verify
echo "[6/6] Verifying deployment..."
sleep 5

HEALTH=$(curl -s http://localhost:3000/api/health 2>/dev/null || echo '{"error":"not ready"}')
echo "  Health check: $HEALTH"

echo ""
echo "========================================="
echo "  SOFIE is running!"
echo "========================================="
echo ""
echo "  Web UI:    http://localhost:3000"
echo "  API:       http://localhost:3000/api/health"
echo ""
echo "  To expose to the internet:"
echo "    Option 1: Use the Vast.ai/RunPod port forwarding"
echo "    Option 2: cloudflared tunnel --url http://localhost:3000"
echo ""
echo "  To update:"
echo "    git pull origin main"
echo "    docker compose build sofie"
echo "    docker compose up -d sofie"
echo ""
echo "  To stop:"
echo "    docker compose down"
echo ""
