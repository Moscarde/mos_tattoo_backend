# Dicionário de Modelos de Dados

Este documento detalha os principais modelos do banco de dados, suas responsabilidades e regras de negócio associadas.

## 1. App: `accounts`

### `Profile`
Extensão do modelo padrão de usuário (`auth.User`). Centraliza as informações de perfil e permissões de negócio.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `user` | OneToOne | Relacionamento com o usuário de autenticação do Django. |
| `role` | CharField | Papel do usuário: `ADMIN_TECNICO`, `GERENTE_GERAL`, `GERENTE_UNIDADE`. |
| `unidades` | ManyToMany | Lista de Unidades que o usuário pode gerenciar (relevante para Gerentes de Unidade). |

**Regras de Negócio:**
-   **Hierarquia de Acesso**:
    -   `ADMIN_TECNICO` e `GERENTE_GERAL`: Visualizam dados de TODAS as unidades.
    -   `GERENTE_UNIDADE`: Visualiza dados APENAS das unidades listadas no campo `unidades`.

---

## 2. App: `core`

### `Unidade`
Representa uma loja física, filial ou unidade de negócio da franquia.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `nome` | CharField | Nome fantasia da unidade. |
| `codigo` | CharField | Identificador único de negócio (ex: "SP-001"). Usado em filtros de integração. |
| `ativa` | Boolean | Soft delete. Unidades inativas não aparecem nos dashboards. |

---

## 3. App: `dashboards`

### `Connection`
Credenciais de acesso a bancos de dados externos (PostgreSQL) para execução de queries analíticas.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `host`, `port`, `db` | Char/Int | Dados de conexão TCP/IP. |
| `usuario`, `senha` | Char | Credenciais (a senha deve ser armazenada de forma segura/encriptada). |

### `DataSource`
Define um **Dataset Base** (Fonte de Dados). Na nova arquitetura, representa uma tabela ou view "crua", sem agregações.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `sql` | TextField | Query SQL base (ex: `SELECT * FROM sales`). Deve ser _stateless_. |
| `connection` | FK | Banco de dados onde a query será executada. |
| `columns_metadata` | JSON | Metadados extraídos automaticamente (tipos de dados, semântica). |

**Regras de Negócio:**
-   **Segurança**: A query SQL não pode conter `;` ou comandos DML (`INSERT`, `UPDATE`, `DROP`) para evitar SQL Injection.
-   **Imutabilidade**: O DataSource não define "somas" ou "médias", apenas disponibiliza colunas para serem agregadas posteriormente.

### `DashboardTemplate`
Define o "desenho" global de um dashboard. É o esqueleto que será replicado para várias unidades.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `schema` | JSON | Layout do dashboard (grid system, posicionamento). |
| `filterable_fields` | JSON | Configuração de filtros globais (ex: Filtro de Data, Filtro de Vendedor). |

### `DashboardBlock`
Representa um único gráfico ou componente visual dentro de um template.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `template` | FK | Dashboard ao qual pertence. |
| `datasource` | FK | Fonte dos dados brutos. |
| `chart_type` | Enum | Tipo visual: `bar`, `line`, `pie`, `metric`, `table`. |
| `x_axis_field` | String | Campo usado no eixo X (dimensão temporal ou categórica). |
| `y_axis_aggregations` | JSON | Lista de métricas (ex: `SUM(valor)`, `COUNT(id)`). |

**Conceito Chave**:
O `DashboardBlock` é a regra de negócio analítica. Ele diz ao `QueryBuilder` como transformar os dados do `DataSource` em informações visuais.

### `DashboardInstance`
A materialização de um `DashboardTemplate` para uma `Unidade` específica.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `template` | FK | O modelo visual a ser usado. |
| `unidade` | FK | A unidade de negócio dona dos dados. |
| `filtro_sql` | Text | Cláusula WHERE adicional injetada automaticamente (ex: `unidade_id = 5`). |
| `usuarios_com_acesso`| ManyToMany | Controle fino de quais usuários veem esta instância específica. |

**Regra de Negócio:**
-   Quando um usuário acessa um dashboard, o sistema busca a `DashboardInstance` correspondente à unidade dele.
-   O `filtro_sql` é **obrigatório** em ambientes multi-tenant para garantir isolamento de dados entre unidades.
