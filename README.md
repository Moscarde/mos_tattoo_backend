# Dashboard Backend - Sistema BI Interno

Backend Django para dashboards gerenciais com controle de acesso por unidade.

## 🎯 O que é

Sistema de BI/Analytics (apenas leitura) com:
- Templates de dashboards reutilizáveis
- Controle de acesso por papéis e unidades
- Queries SQL seguras (apenas SELECT)
- API REST + Django Admin

## 🚀 Quick Start

```bash
# Subir containers
./manage.sh up

# Criar dados iniciais (grupos, permissões, unidades, usuários)
./manage.sh shell "python manage.py setup_initial_data"
```

Acesse: http://localhost:8000/admin/

**Usuários criados:**
- `admin_tecnico` / `admin123` - Administrador com acesso total
- `gerente_geral` / `gerente123` - Gerente geral
- `gerente_unidade_sp` / `gerente123` - Gerente da unidade SP-01

## 🛠️ Stack

- Django 4.2 LTS + DRF
- PostgreSQL
- JWT Authentication
- Docker + Docker Compose

## 🏗️ Arquitetura

### Apps

**Core** - Modelo `Unidade` (lojas/filiais)

**Accounts** - `Profile` com papéis:
- `ADMIN_TECNICO` - Acesso total
- `GERENTE_GERAL` - Todas unidades
- `GERENTE_UNIDADE` - Suas unidades

**Dashboards** - 3 modelos:
- `DashboardTemplate` - Template com schema JSON
- `DashboardInstance` - Instância por unidade
- `DataSource` - Queries SQL (validação automática)

## 🔌 API

```bash
# Login
POST /api/auth/login/
{"username": "admin", "password": "admin123"}

# Dashboards do usuário
GET /api/dashboards/

# Dados de um dashboard
GET /api/dashboards/{id}/data/
```

## 📦 Instalação

### Com Docker (Recomendado)

```bash
# Inicia tudo
./manage.sh up

# Ver logs
./manage.sh logs

# Parar
./manage.sh down

# Outros comandos
./manage.sh  # mostra ajuda
```

### Sem Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure .env (mude DB_HOST para localhost)
cp .env.example .env

# Crie o banco
createdb mos_tattoo_db

# Migre e rode
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## 👨‍💼 Usando o Admin

### Bootstrap de Dados Iniciais

O sistema possui uma command de gerenciamento para criar dados iniciais automaticamente:

```bash
# Com Docker
./manage.sh shell "python manage.py setup_initial_data"

# Sem Docker
python manage.py setup_initial_data
```

**O que é criado:**

**Grupos e Permissões:**
- `ADMIN_TECNICO` - Todas as permissões do Django Admin
- `GERENTE_GERAL` - Sem permissões de admin (acesso via API)
- `GERENTE_UNIDADE` - Sem permissões de admin (acesso via API)

**Unidades:**
- São Paulo (SP-01)
- Rio de Janeiro (RJ-01)
- Belo Horizonte (BH-01)
- Curitiba (CT-01)
- Porto Alegre (POA-01)

**Usuários de Exemplo:**
| Usuário | Senha | Grupo | Acesso Admin | Unidades |
|---------|-------|-------|--------------|----------|
| admin_tecnico | admin123 | ADMIN_TECNICO | ✓ Sim (superuser) | Todas |
| gerente_geral | gerente123 | GERENTE_GERAL | ✗ Não (API) | Todas |
| gerente_unidade_sp | gerente123 | GERENTE_UNIDADE | ✗ Não (API) | SP-01 |

**Opções da command:**
```bash
# Pular criação de usuários (só criar grupos e unidades)
python manage.py setup_initial_data --skip-users

# Ver ajuda
python manage.py setup_initial_data --help
```

> 💡 **A command é idempotente**: pode ser executada múltiplas vezes sem duplicar dados.

### Criação Manual de Recursos

1. **Criar Unidades** → Admin > Core > Unidades

2. **Criar DataSource** → Admin > Dashboards > Fontes de Dados
   ```sql
   SELECT produto, SUM(valor) as total
   FROM fat_vendas
   WHERE unidade_id = %(unidade_id)s
   GROUP BY produto
   ```

3. **Criar Template** → Admin > Dashboards > Templates
   ```json
   {
     "blocks": [{
       "type": "chart",
       "dataSource": "vendas_produto"
     }]
   }
   ```

4. **Criar Instância** → Associar template + unidade

5. **Criar Usuários** → Configure papel e unidades

## 📊 Próximos Passos

- [ ] Implementar execução de queries no endpoint `/dashboards/{id}/data/`
- [ ] Sistema de cache para queries
- [ ] Logs de auditoria
- [ ] Filtros dinâmicos
- [ ] Exportação (CSV, Excel)
- [ ] Testes automatizados

---

**Projeto de Portfólio** - Demonstração de arquitetura Django/DRF para sistemas de BI
