# Use uma imagem base Python oficial
FROM python:3.13-slim

ENV PYTHONUNBUFFERED 1
WORKDIR /usr/src/app

# Instala as dependências de sistema necessárias para compilar psycopg2
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie o restante do código do projeto
COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "core.wsgi:application"]