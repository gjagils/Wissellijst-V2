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

    echo "1/4 Code ophalen..."
    git pull origin main
    info "Code bijgewerkt"

    echo "2/4 Docker image bouwen..."
    sudo docker build --no-cache -t "$IMAGE" .
    info "Image gebouwd"

    echo "3/4 Container herstarten..."
    sudo docker stop "$CONTAINER" 2>/dev/null || true
    sudo docker rm "$CONTAINER" 2>/dev/null || true
    sudo docker run -d \
      --name "$CONTAINER" \
      --env-file .env \
      -v /volume1/docker/wissellijst-v2/data:/app/data \
      -p 9090:5000 \
      --restart unless-stopped \
      "$IMAGE"
    info "Container draait"

    echo "4/4 Opruimen..."
    sudo docker image prune -f
    info "Klaar! App beschikbaar op poort 9090"
    ;;

  restart)
    echo "=== Container herstarten ==="
    sudo docker restart "$CONTAINER"
    info "Container herstart"
    ;;

  logs)
    echo "=== Logs (Ctrl+C om te stoppen) ==="
    sudo docker logs -f --tail 50 "$CONTAINER"
    ;;

  status)
    echo "=== Status ==="
    if sudo docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
      info "Container draait"
      sudo docker ps --filter "name=$CONTAINER" --format "table {{.Status}}\t{{.Ports}}"
    else
      error "Container draait niet"
    fi
    ;;

  shell)
    echo "=== Shell in container ==="
    sudo docker exec -it "$CONTAINER" /bin/bash
    ;;

  backup)
    echo "=== Data backup ==="
    BACKUP_FILE="/volume1/docker/wissellijst-v2/backup_$(date +%Y%m%d_%H%M%S).tar.gz"
    sudo tar -czf "$BACKUP_FILE" -C /volume1/docker/wissellijst-v2 data/
    info "Backup: $BACKUP_FILE"
    ;;

  help|*)
    echo "Wissellijst V2 - Deploy script"
    echo ""
    echo "Gebruik: ./deploy.sh <commando>"
    echo ""
    echo "Commando's:"
    echo "  update    Git pull, image bouwen, container herstarten"
    echo "  restart   Alleen container herstarten"
    echo "  logs      Live logs bekijken"
    echo "  status    Kijken of de container draait"
    echo "  shell     Shell openen in de container"
    echo "  backup    Data directory backuppen"
    echo ""
    ;;

esac
