#!/bin/bash
# Wissellijst V2 - Deploy script voor Synology
# Gebruik: ./deploy.sh [commando]
#
# Voer uit vanuit de project directory:
#   cd /volume1/docker/WissellijstV2 && ./deploy.sh update

set -e

CONTAINER="wissellijst-v2"
IMAGE="wissellijst-v2:latest"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Kleurtjes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!!]${NC} $1"; }
error() { echo -e "${RED}[FOUT]${NC} $1"; }

case "${1:-help}" in

  update)
    echo "=== Wissellijst V2 updaten ==="
    cd "$PROJECT_DIR"

    echo "1/3 Code ophalen..."
    git pull origin main
    info "Code bijgewerkt"

    echo "2/3 Docker image bouwen..."
    docker build --no-cache -t "$IMAGE" .
    info "Image gebouwd"

    echo "3/3 Opruimen..."
    docker image prune -f
    info "Image klaar! Herstart nu via Portainer of: ./deploy.sh restart"
    ;;

  restart)
    echo "=== Container herstarten met nieuw image ==="
    # Stop, verwijder, en herstart met dezelfde config via Portainer env vars
    # Env vars ophalen uit de draaiende container
    ENV_ARGS=""
    if docker inspect "$CONTAINER" > /dev/null 2>&1; then
      ENV_ARGS=$(docker inspect "$CONTAINER" --format '{{range .Config.Env}}-e {{.}} {{end}}')
    else
      error "Container '$CONTAINER' niet gevonden. Start via Portainer."
      exit 1
    fi
    docker stop "$CONTAINER" 2>/dev/null || true
    docker rm "$CONTAINER" 2>/dev/null || true
    eval docker run -d \
      --name "$CONTAINER" \
      $ENV_ARGS \
      -v /volume1/docker/wissellijst-v2/data:/app/data \
      -p 9090:5000 \
      --restart unless-stopped \
      "$IMAGE"
    info "Container herstart met nieuw image"
    ;;

  logs)
    echo "=== Logs (Ctrl+C om te stoppen) ==="
    docker logs -f --tail 50 "$CONTAINER"
    ;;

  status)
    echo "=== Status ==="
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
      info "Container draait"
      docker ps --filter "name=$CONTAINER" --format "table {{.Status}}\t{{.Ports}}"
    else
      error "Container draait niet"
    fi
    ;;

  shell)
    echo "=== Shell in container ==="
    docker exec -it "$CONTAINER" /bin/bash
    ;;

  backup)
    echo "=== Data backup ==="
    BACKUP_FILE="/volume1/docker/wissellijst-v2/backup_$(date +%Y%m%d_%H%M%S).tar.gz"
    tar -czf "$BACKUP_FILE" -C /volume1/docker/wissellijst-v2 data/
    info "Backup: $BACKUP_FILE"
    ;;

  help|*)
    echo "Wissellijst V2 - Deploy script"
    echo ""
    echo "Gebruik: ./deploy.sh <commando>"
    echo ""
    echo "Commando's:"
    echo "  update    Git pull + image bouwen"
    echo "  restart   Container herstarten met nieuw image (env vars uit Portainer)"
    echo "  logs      Live logs bekijken"
    echo "  status    Kijken of de container draait"
    echo "  shell     Shell openen in de container"
    echo "  backup    Data directory backuppen"
    echo ""
    echo "Typisch gebruik na code-wijziging:"
    echo "  ./deploy.sh update && ./deploy.sh restart"
    echo ""
    ;;

esac
