#!/bin/bash
set -e

echo "⏳ Aguardando PostgreSQL..."
while ! nc -z db 5432; do
  sleep 0.5
done
echo "✓ PostgreSQL pronto!"

echo "⏳ Executando migrações..."
python manage.py migrate --noinput

echo "⏳ Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

# Cria superusuário automático
if [ "$DJANGO_SUPERUSER_USERNAME" ]; then
    python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists():
    User.objects.create_superuser('$DJANGO_SUPERUSER_USERNAME', '$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PASSWORD')
    print('✓ Superusuário criado!')
END
fi

echo "🚀 Iniciando servidor..."
python manage.py runserver 0.0.0.0:8000
