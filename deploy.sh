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
STACK_FILE="$PROJECT_DIR/portainer-stack.yml"

# Kleurtjes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!!]${NC} $1"; }
error() { echo -e "${RED}[FOUT]${NC} $1"; }

# Env vars uit draaiende Portainer container halen en als .env opslaan
ENV_FILE="$PROJECT_DIR/.env"
ENV_KEYS="SPOTIFY_CLIENT_ID SPOTIFY_CLIENT_SECRET SPOTIFY_REDIRECT_URI OPENAI_API_KEY"

sync_env() {
  if ! docker inspect "$CONTAINER" > /dev/null 2>&1; then
    error "Container '$CONTAINER' niet gevonden. Kan env vars niet ophalen."
    exit 1
  fi
  echo "# Auto-generated from Portainer container env vars" > "$ENV_FILE"
  for KEY in $ENV_KEYS; do
    VALUE=$(docker inspect "$CONTAINER" --format "{{range .Config.Env}}{{println .}}{{end}}" | grep "^${KEY}=" | head -1)
    if [ -n "$VALUE" ]; then
      echo "$VALUE" >> "$ENV_FILE"
    fi
  done
  info ".env aangemaakt vanuit Portainer container"
}

case "${1:-help}" in

  deploy)
    echo "=== Wissellijst V2 - Volledige deploy ==="
    cd "$PROJECT_DIR"

    echo "1/4 Code ophalen..."
    git pull origin main
    info "Code bijgewerkt"

    echo "2/4 Docker image bouwen..."
    docker build --no-cache -t "$IMAGE" .
    info "Image gebouwd"

    echo "3/4 Opruimen..."
    docker image prune -f
    info "Oude images opgeruimd"

    echo "4/5 Env vars ophalen uit Portainer container..."
    sync_env

    echo "5/5 Container herstarten via stack..."
    docker compose -f "$STACK_FILE" --env-file "$ENV_FILE" up -d --force-recreate
    info "Container herstart via stack met .env variabelen"

    echo ""
    info "Deploy compleet! App draait op poort 9090"
    docker ps --filter "name=$CONTAINER" --format "table {{.Status}}\t{{.Ports}}"
    ;;

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
    echo "=== Container herstarten via stack ==="
    cd "$PROJECT_DIR"
    sync_env
    docker compose -f "$STACK_FILE" --env-file "$ENV_FILE" up -d --force-recreate
    info "Container herstart via stack met .env variabelen"
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
    echo "  deploy    Alles in 1x: pull + build + restart"
    echo "  update    Alleen git pull + image bouwen"
    echo "  restart   Alleen container herstarten met nieuw image"
    echo "  logs      Live logs bekijken"
    echo "  status    Kijken of de container draait"
    echo "  shell     Shell openen in de container"
    echo "  backup    Data directory backuppen"
    echo ""
    echo "Typisch gebruik na code-wijziging:"
    echo "  ./deploy.sh deploy"
    echo ""
    ;;

esac
