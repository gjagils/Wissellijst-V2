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

ENV_FILE="$PROJECT_DIR/.env"

case "${1:-help}" in

  update)
    echo "=== Wissellijst V2 updaten ==="
    cd "$PROJECT_DIR"

    # Check of .env bestaat
    if [ ! -f "$ENV_FILE" ]; then
      error ".env bestand ontbreekt!"
      echo ""
      echo "Maak het aan met: ./deploy.sh setup"
      exit 1
    fi

    echo "1/4 Code ophalen..."
    git pull origin main
    info "Code bijgewerkt"

    echo "2/4 Docker image bouwen..."
    docker build --no-cache -t "$IMAGE" .
    info "Image gebouwd"

    echo "3/4 Container herstarten..."
    docker stop "$CONTAINER" 2>/dev/null || true
    docker rm "$CONTAINER" 2>/dev/null || true
    docker run -d \
      --name "$CONTAINER" \
      --env-file "$ENV_FILE" \
      -v /volume1/docker/wissellijst-v2/data:/app/data \
      -p 9090:5000 \
      --restart unless-stopped \
      "$IMAGE"
    info "Container draait"

    echo "4/4 Opruimen..."
    docker image prune -f
    info "Klaar! App beschikbaar op poort 9090"
    ;;

  restart)
    echo "=== Container herstarten ==="
    docker restart "$CONTAINER"
    info "Container herstart"
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

  setup)
    echo "=== .env bestand aanmaken ==="
    if [ -f "$ENV_FILE" ]; then
      warn ".env bestaat al. Bewerk met: nano $ENV_FILE"
      exit 0
    fi
    cat > "$ENV_FILE" << 'ENVEOF'
# Spotify API (https://developer.spotify.com/dashboard)
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
SPOTIFY_REDIRECT_URI=http://JOUW-SYNOLOGY-IP:9090/callback

# OpenAI API (https://platform.openai.com/api-keys)
OPENAI_API_KEY=
ENVEOF
    info ".env aangemaakt: $ENV_FILE"
    echo ""
    echo "Vul nu je API keys in:"
    echo "  nano $ENV_FILE"
    echo ""
    echo "Daarna kun je deployen met: ./deploy.sh update"
    ;;

  help|*)
    echo "Wissellijst V2 - Deploy script"
    echo ""
    echo "Gebruik: ./deploy.sh <commando>"
    echo ""
    echo "Commando's:"
    echo "  setup     .env bestand aanmaken (eenmalig)"
    echo "  update    Git pull, image bouwen, container herstarten"
    echo "  restart   Alleen container herstarten"
    echo "  logs      Live logs bekijken"
    echo "  status    Kijken of de container draait"
    echo "  shell     Shell openen in de container"
    echo "  backup    Data directory backuppen"
    echo ""
    ;;

esac
