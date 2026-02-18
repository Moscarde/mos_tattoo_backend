# Contratos da API - MOS Tattoo Backend

Guia de referência para integração Frontend. Todas as respostas são em formato JSON.

**Base URL**: `/api/`

## Autenticação

O sistema utiliza autenticação via JWT (Json Web Token). O token deve ser enviado no header `Authorization` de todas as requisições protegidas.

**Header:**
`Authorization: Bearer <seu_token_de_acesso>`

### 1. Login (Obter Token)
Gera o par de chaves de acesso (access e refresh).

-   **URL**: `/auth/login/`
-   **Método**: `POST`
-   **Body**:
    ```json
    {
      "username": "usuario.teste",
      "password": "senha_secreta"
    }
    ```
-   **Response (200 OK)**:
    ```json
    {
      "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1...",
      "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1..."
    }
    ```

### 2. Refresh Token
Renova o token de acesso expirado usando o refresh token.

-   **URL**: `/auth/refresh/`
-   **Método**: `POST`
-   **Body**:
    ```json
    {
      "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1..."
    }
    ```

---

## Analytics & Dashboards

### 3. Listar Dashboards Disponíveis
Retorna a lista de dashboards que o usuário logado tem permissão para acessar.

-   **URL**: `/dashboards/`
-   **Método**: `GET`
-   **Response (200 OK)**:
    ```json
    [
      {
        "id": "a1b2c3d4-...",
        "template_nome": "Vendas Mensais",
        "unidade_nome": "Unidade Paulista",
        "unidade_codigo": "SP-001",
        "filtro_sql_preview": "unidade_id = 15...",
        "ativo": true
      },
      ...
    ]
    ```

### 4. Obter Dados do Dashboard (Full Load)
Retorna a estrutura completa e os dados de um dashboard específico.
**Nota**: Este endpoint pode ser pesado pois executa múltiplas queries.

-   **URL**: `/dashboards/{id}/data-legacy/` (Legado) ou `/dashboards/{id}/data/` (Novo)
-   **Método**: `GET`
-   **Response (200 OK)**:
    ```json
    {
      "id": "a1b2c3d4-...",
      "template_nome": "Vendas Mensais",
      "unidade": {
        "id": "...",
        "nome": "Unidade Paulista",
        "codigo": "SP-001"
      },
      "schema": {
        "layout": "grid",
        "columns": 12
      },
      "data": {
        "faturamento_block": {
          "type": "bar-chart",
          "data": [
            { "mes": "Jan", "total": 15000 },
            { "mes": "Fev", "total": 18000 }
          ]
        },
        "kpi_vendas_block": {
          "type": "metric",
          "data": [
            { "total_periodo": 33000 }
          ]
        }
      }
    }
    ```

### 5. Obter Dados de um Bloco Específico (Lazy Load)
Endpoint otimizado para carregar gráficos individualmente ou atualizar apenas um widget.

-   **URL**: `/dashboard-blocks/{id}/data/`
-   **Método**: `GET`
-   **Response (200 OK)**:
    ```json
    {
      "success": true,
      "data": {
        "x": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "series": [
            {
                "axis": "y1",
                "label": "Receita Total",
                "values": [1200.50, 1350.00, 900.25]
            },
            {
                "axis": "y2",
                "label": "Novos Clientes",
                "values": [5, 8, 3]
            }
        ]
      }
    }
    ```
    -   `x`: Array com os labels do eixo X (categorias ou datas).
    -   `series`: Array de objetos, onde cada um representa uma linha/barra no gráfico.

### 6. Listar DataSources (Fontes de Dados)
Lista os datasets base disponíveis para criação de novos blocos.

-   **URL**: `/datasources/`
-   **Método**: `GET`
-   **Response (200 OK)**:
    ```json
    [
        {
            "id": "...",
            "nome": "Vendas Consolidadas",
            "connection_nome": "Banco Produção",
            "sql": "SELECT * FROM public.sales_mart",
            "ativo": true
        }
    ]
    ```

---

## Códigos de Erro Comuns

| Código | Descrição |
|--------|-----------|
| `401 Unauthorized` | Token ausente, inválido ou expirado. |
| `403 Forbidden` | Usuário logado não tem permissão para acessar este recurso (ex: dashboard de outra unidade). |
| `404 Not Found` | Recurso (ID) não existe. |
| `400 Bad Request` | Parâmetros inválidos ou erro de validação na query. |
| `500 Internal Server Error` | Erro não tratado no servidor (possível falha de conexão com banco de dados analítico). |
