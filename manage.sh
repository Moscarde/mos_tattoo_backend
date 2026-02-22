#!/bin/bash
set -e

usage() {
    echo "Uso: ./manage.sh [comando]"
    echo ""
    echo "Comandos:"
    echo "  up        - Deploy limpo (apenas estrutura, sem dados)"
    echo "  up-demo   - Deploy com dados de demonstração pré-carregados"
    echo "  down      - Para os containers"
    echo "  logs      - Exibe logs"
    echo "  shell     - Acessa shell do Django"
    echo "  bash      - Acessa bash do container"
    echo "  db        - Acessa PostgreSQL"
    echo "  clean     - Remove tudo (apaga dados e volumes)"
    echo ""
    echo "Modos de deploy:"
    echo "  clean  → ./manage.sh up        (DB vazio, apenas superuser admin/admin123)"
    echo "  demo   → ./manage.sh up-demo   (DB pré-populado com dados fictícios)"
    echo ""
}

case "$1" in
    up)
        [ ! -f .env ] && cp .env.example .env
        # Garante modo limpo (sem demo)
        sed -i 's/^DEMO_MODE=.*/DEMO_MODE=false/' .env
        docker compose up -d --build
        echo "✓ Deploy limpo. Acesse: http://localhost:8000/admin/ (admin/admin123)"
        ;;
    up-demo)
        [ ! -f .env ] && cp .env.example .env
        # Habilita modo demo
        sed -i 's/^DEMO_MODE=.*/DEMO_MODE=true/' .env
        docker compose up -d --build
        echo "✓ Deploy demo. Acesse: http://localhost:8000/admin/ (admin/admin123)"
        echo "  Usuários disponíveis: admin_tecnico/admin123, gerente_geral/gerente123, gerente_unidade_sp/gerente123"
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
