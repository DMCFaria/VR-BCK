# Use uma imagem base Python oficial (como antes)
FROM python:3.13-slim

ENV PYTHONUNBUFFERED 1
WORKDIR /usr/src/app

# --- PASSO NOVO E CRUCIAL ---
# Instala as dependências de sistema necessárias para compilar psycopg2
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*
# ----------------------------

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie o restante do código do projeto
COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "seu_projeto.wsgi:application"]