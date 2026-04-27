# VR-BCK - Backend de Gestão de Benefícios

API REST para gestão de benefícios de funcionários (Vale Refeição).

## Tecnologias

- **Framework:** Django 5.2 + Django REST Framework
- **Autenticação:** JWT (Simple JWT)
- **Banco de Dados:** PostgreSQL
- **Processamento:** Pandas, NumPy (manipulação de arquivos Excel)
- **Tarefas Assíncronas:** Celery + Redis
- **Armazenamento:** AWS S3
- **Container:** Docker + Gunicorn

## Estrutura do Projeto

```
VR-BCK/
├── core/              # Configurações Django (settings, urls, wsgi, asgi, celery)
├── users/             # Autenticação e gestão de usuários
├── entidades/         # Cadastro de administradoras, condomínios e funcionários
├── beneficios/        # Catálogo de produtos e movimentações
├── upload/            # Upload, processamento de Excel, PDF e exports
│   ├── tasks.py       # Tarefas Celery
│   ├── pdf_reader.py  # Leitura de PDFs de boleto/nota dédito
│   ├── faturamento.py # Upload de faturamento
├── docs/              # Documentação de integração
├── manage.py
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Configuração

### Variáveis de Ambiente (.env)

```env
DB_USER=seu_usuario
DB_PASSWORD=sua_senha
DB_HOST=seu_host
DB_PORT=sua_porta
DB_NAME=nome_banco
SECRET_KEY=sua_chave_secreta

# AWS S3
ACCESS_KEY_S3=sua_access_key
SECRET_KEY_S3=sua_secret_key
BUCKET_S3=nome_do_bucket

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Instalação Local

```bash
python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Executando Celery (Processamento em Background)

```bash
# Terminal 1 - Redis
redis-server

# Terminal 2 - Worker Celery
celery -A core worker -l info
```

### Docker

```bash
docker-compose up --build
```

Isso cria os serviços: web, celery, redis e db.

---

## Fluxo de Trabalho

### 1. Upload de Movimentações (Excel)

1. Upload do arquivo Excel com movimentações
2. Extração dos dados (parsing)
3. Confirmação com dados corrigidos
4. Criação de condomínios, funcionários e movimentações

**Endpoints:**
- `POST /api/upload/` - Upload Excel
- `POST /api/upload/confirm/` - Confirmar dados processados

**Payload de Confirmação:**
```json
{
    "file_upload_id": 1,
    "condominios": [...],
    "data_vencimento": "2026-04-10",
    "vigencia_inicio": "2026-04-01",
    "vigencia_fim": "2026-04-30"
}
```

---

### 2. Upload de Faturamento (PDF - Assíncrono)

Sistema de upload de documentos de faturamento (boleto, nota de débito, nota fiscal) com processamento em background utilizando Celery.

#### Fluxo:
1. Frontend envia arquivos PDF via POST
2. Backend cria/atualiza registro Faturamento (mesmo ID da importação)
3. Task Celery processa em background:
   - Lê PDFs e extrai CNPJs
   - Separa páginas por condomínio
   - Faz upload individual para S3
   - Salva documentos no banco
4. Frontend faz polling no endpoint de status

**Regras:**
- `importacao_id` = `faturamento_id` (mesmo valor)
- Se já existir faturamento para a importação, apaga o anterior

#### Endpoints:

**Upload:**
- `POST /api/upload/faturamento/upload/`
- Body: `importacao_id`, `competencia`, `arquivo_boleto`, `arquivo_nota_debito`, `arquivo_nota_fiscal` (opcional)

**Status:**
- `GET /api/upload/faturamento/<id>/status/`

**Status possíveis:**
- `PENDING` - Aguardando processamento
- `PROCESSING` - Processando (campo `progresso`: 0-100%)
- `COMPLETED` - Concluído
- `FAILED` - Falhou

**Response status:**
```json
{
  "faturamento_id": 1,
  "importacao_id": 1,
  "status": "PROCESSING",
  "progresso": 45,
  "competencia": "2026-04-01",
  "criado_em": "2026-04-27T10:30:00Z"
}
```

---

## API Endpoints

### Autenticação
- `POST /api/auth/token/` - Obter token de acesso
- `POST /api/auth/token/refresh/` - Renovar token
- `POST /api/auth/token/verify/` - Verificar token

### Usuários
- `POST /api/users/login/` - Login de usuário
- `POST /api/users/register/` - Registrar usuário
- `GET /api/users/me/` - Usuário atual

### Entidades
- `/api/entidades/administradoras/` - Administradoras
- `/api/entidades/condominios/` - Condomínios
- `/api/entidades/funcionarios/` - Funcionários
- `/api/entidades/gerentes/` - Gerentes
- `/api/entidades/vinculos/` - Vínculos

### Benefícios
- `/api/beneficios/produtos/` - Catálogo de produtos
- `/api/beneficios/movimentacoes/` - Movimentações
- `/api/beneficios/importacoes/` - Histórico de importações
- `/api/beneficios/importacoes/ultima/` - Última importação

### Upload
- `POST /api/upload/` - Upload Excel
- `POST /api/upload/confirm/` - Confirmar dados
- `POST /api/upload/faturamento/upload/` - Upload faturamento (assíncrono)
- `GET /api/upload/faturamento/<id>/status/` - Status faturamento
- `GET /api/upload/export/faturamento/` - Exportar planilha
- `GET /api/upload/download-excel-template/` - Baixar template

---

## Modelos

### Importacao (beneficios)
- `id`: ID único (também usado como faturamento_id)
- `file_upload`: FK para FileUpload
- `usuario`: FK para usuário
- `data_importacao`: Data/hora da importação
- `status`: PENDING/PROCESSING/COMPLETED/FAILED
- `total_registros`: Total de registros no arquivo
- `registros_processados`: Registros processados com sucesso
- `erros`: Lista de erros
- `url`: URL do arquivo processado
- `data_vencimento`: Data de vencimento do faturamento
- `vigencia_inicio`: Início da vigência
- `vigencia_fim`: Fim da vigência

### Faturamento (beneficios)
- `id`: ID único (mesmo que importacao_id)
- `importacao`: FK para Importacao
- `competencia`: Data (YYYY-MM-DD)
- `status`: PENDING/PROCESSING/COMPLETED/FAILED
- `progresso`: Inteiro 0-100
- `criado_por`: Usuário que iniciou
- `criado_em`: Data de criação

### FaturamentoDocumento (beneficios)
- `faturamento`: FK para Faturamento
- `condominio`: FK para Condomínio
- `url_boleto`: URL S3 do PDF
- `url_nota_debito`: URL S3 do PDF
- `url_nota_fiscal`: URL S3 do PDF (opcional)

---

## Processamento de PDF

### Leitura de Boleto
- Extrai CNPJs do formato: `CNPJ: XX.XXX.XXX-XXXX-XX`
- Separa páginas por condomínio

### Leitura de Nota de Débito
- Extrai CNPJs do formato: `XX.XXX.XXX/0001-XX`
- Associa páginas aos condomínios

---

## Testes

```bash
python manage.py test
```

---

## Licença

Proprietário - FedCorp