# Template-Based BI Distribution | Backend Engine (API)

Este serviço é o **núcleo de inteligência** do ecossistema [Template-Based BI Distribution](https://github.com/Moscarde/Template-Based-BI-Distribution) — uma Prova de Conceito que valida uma arquitetura de distribuição escalável de dashboards analíticos através de templates instanciáveis e permissionamento dinâmico.

> 🔗 **Repositório Central**: Para entender o contexto completo da arquitetura, acesse o [repositório principal](https://github.com/Moscarde/Template-Based-BI-Distribution).

---

## 🚀 Visão Geral

O backend atua como uma **Headless BI Engine**: toda a lógica de composição, segurança e agregação de dados reside aqui, servindo metadados e payloads prontos para consumo por qualquer frontend.

A proposta resolve o clássico "caos da replicação" — a necessidade de manter dezenas de cópias do mesmo dashboard, diferenciadas apenas pelo filtro de unidade. Nesta arquitetura, N dashboards são definidos como templates, e cada instância é gerada dinamicamente com seu próprio contexto de segurança e filtro, sem duplicação de código ou estrutura. Alterações no template se refletem automaticamente em todas as instâncias, garantindo **consistência e agilidade** na manutenção.

### Principais Características

- **Semantic Layer (Camada Semântica)**: Abstração que separa os dados brutos (`DataSources`) da intenção de visualização (`Charts`), permitindo a construção dinâmica de queries SQL seguras e parametrizadas.
- **Template Engine**: Um template de dashboard é definido uma única vez e instanciado N vezes, cada instância com seu próprio contexto de filtro e permissão.
- **Row Level Context**: Filtros de segurança são injetados antes do processamento da query, garantindo isolamento entre unidades sem lógica no frontend.
- **Arquitetura Multi-tenant**: Isolamento lógico de dados por unidade de negócio via configuração, sem duplicação de código ou estrutura.
- **Controle de Acesso Granular (RBAC)**: Perfis diferenciados — Admin Técnico, Gerente Geral e Gerente de Unidade — com níveis distintos de acesso e visibilidade.
- **API RESTful**: Endpoints padronizados para integração com qualquer frontend moderno (React, Vue, Next.js, mobile).

---

## 📦 Estrutura do Repositório

Este repositório disponibiliza **duas versões** do ambiente:

| Versão | Descrição |
|---|---|
| **Clean** | Apenas os models e a estrutura da engine, sem dados. Ideal para adaptar a engine ao seu próprio domínio. |
| **Demo** | Ambiente pré-populado com dados fictícios de uma rede de estúdios (mock temático), pronto para exploração visual dos dashboards. |

> A temática da Demo (dados de uma rede de estúdios de tatuagem) foi escolhida exclusivamente para viabilizar uma exploração rica de gráficos e métricas variadas. Ela não representa o domínio de aplicação da engine. Para o uso completo da demo, é necessario a configuração do [frontend](https://github.com/Moscarde/mos_tattoo_frontend) e do [banco de dados](https://github.com/Moscarde/mos_tattoo_database).

---

## 📚 Documentação Técnica

Para detalhes aprofundados sobre a implementação, consulte a pasta `docs/`:

- [🏛️ Arquitetura do Sistema](docs/ARCHITECTURE.md): Fluxo de dados, Camada Semântica e decisões de design.
- [💾 Dicionário de Modelos](docs/MODELS.md): Explicação detalhada das entidades e regras de negócio.
- [🔌 Contratos da API](docs/API_CONTRACTS.md): Guia de referência dos endpoints para desenvolvedores Frontend.

---

## 🛠️ Como Rodar o Projeto

**Pré-requisitos:** Docker e Docker Compose.

### Deploy Limpo (estrutura sem dados)

Ideal para adaptar a engine ao seu próprio domínio. Apenas migrations são aplicadas — o banco inicia vazio exceto pelo superuser de acesso ao admin.

```bash
./manage.sh up
```

Acesse: `http://localhost:8000/admin/` → `admin / admin123`

---

### Deploy Demo (dados fictícios pré-carregados)

Ambiente completo com conexões, templates, blocos e instâncias de dashboard já configurados, usando dados de uma rede fictícia de estúdios de tatuagem.

```bash
./manage.sh up-demo
```

Acesse: `http://localhost:8000/admin/` → `admin / admin123`

Usuários de demonstração disponíveis:

| Usuário | Senha | Perfil |
|---|---|---|
| `admin_tecnico` | `admin123` | Admin Técnico (superuser) |
| `gerente_geral` | `gerente123` | Gerente Geral |
| `gerente_unidade_sp` | `gerente123` | Gerente de Unidade (SP-01) |

> Para a experiência completa da demo, configure também o [frontend](https://github.com/Moscarde/mos_tattoo_frontend) e o [banco de dados externo](https://github.com/Moscarde/mos_tattoo_database).

---

### Outros comandos

```bash
./manage.sh down    # Para os containers
./manage.sh logs    # Acompanha os logs em tempo real
./manage.sh shell   # Shell interativo do Django
./manage.sh db      # Acessa o PostgreSQL diretamente
./manage.sh clean   # Remove containers e volumes (⚠️ apaga todos os dados)
```

> Para trocar entre modos sem recriar o ambiente: edite `DEMO_MODE` no `.env` e rode `./manage.sh clean` seguido do comando de deploy desejado.

## 💻 Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.10+ |
| Framework | Django 4.2 & Django Rest Framework |
| Banco de Dados | PostgreSQL |
| Infraestrutura | Docker & Docker Compose |