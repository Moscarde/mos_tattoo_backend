# Quick Start - Dashboard Backend

## 🚀 3 Passos

### 1. Suba o ambiente
```bash
./manage.sh up
```

### 2. Acesse
- **Admin**: http://localhost:8000/admin/
- **User**: `admin` / **Pass**: `admin123`

### 3. Comandos úteis
```bash
./manage.sh logs      # Ver logs
./manage.sh down      # Parar
./manage.sh shell     # Django shell
./manage.sh bash      # Bash
./manage.sh db        # PostgreSQL
./manage.sh clean     # Apagar tudo
```

## 📡 API

```bash
# Login
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Listar dashboards (use o token retornado)
curl http://localhost:8000/api/dashboards/ \
  -H "Authorization: Bearer SEU_TOKEN"
```

## 📖 Documentação completa

Veja [README.md](README.md)
