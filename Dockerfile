FROM python:3.11-slim

# Evita que Python escreva arquivos .pyc
ENV PYTHONDONTWRITEBYTECODE=1
# Garante que a saída do Python seja enviada diretamente ao terminal
ENV PYTHONUNBUFFERED=1

# Define o diretório de trabalho
WORKDIR /app

# Instala dependências do sistema necessárias para psycopg2
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Copia o arquivo de requisitos
COPY requirements.txt /app/

# Instala as dependências Python
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia o projeto
COPY . /app/

# Cria diretório para arquivos estáticos
RUN mkdir -p /app/staticfiles

# Expõe a porta 8000
EXPOSE 8000

# Script de entrada que aguarda o banco estar pronto
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
