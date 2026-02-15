#!/bin/bash
set -e

usage() {
    echo "Uso: ./manage.sh [comando]"
    echo ""
    echo "Comandos:"
    echo "  up      - Inicia os containers"
    echo "  down    - Para os containers"
    echo "  logs    - Exibe logs"
    echo "  shell   - Acessa shell do Django"
    echo "  bash    - Acessa bash do container"
    echo "  db      - Acessa PostgreSQL"
    echo "  clean   - Remove tudo (apaga dados)"
    echo ""
}

case "$1" in
    up)
        [ ! -f .env ] && cp .env.example .env
        docker compose up -d --build
        echo "✓ Acesse: http://localhost:8000/admin/ (admin/admin123)"
        ;;
    down)
        docker compose down
        ;;
    logs)
        docker compose logs -f
        ;;
    shell)
        docker compose exec web python manage.py shell
        ;;
    bash)
        docker compose exec web bash
        ;;
    db)
        docker compose exec db psql -U postgres -d mos_tattoo_db
        ;;
    clean)
        read -p "Apagar todos os dados? (yes/no): " -r
        [[ $REPLY == "yes" ]] && docker compose down -v
        ;;
    *)
        usage
        ;;
esac
