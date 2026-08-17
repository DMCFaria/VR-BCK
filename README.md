# VR-BCK - Backend de Gestão de Benefícios

API REST para gestão de benefícios de funcionários de condomínios: vale refeição/alimentação (VR/VA) e vale transporte (VT), incluindo importação de planilhas, faturamento, emissão de NFS-e, boletos e acompanhamento operacional (Kanban).

## Tecnologias

- **Framework:** Django 5.2 + Django REST Framework
- **Autenticação:** JWT (Simple JWT) + login com Google
- **Documentação:** drf-spectacular (OpenAPI 3 / Swagger UI / ReDoc)
- **Banco de Dados:** PostgreSQL
- **Processamento:** Pandas, NumPy, openpyxl (Excel), pypdf (PDF)
- **Tarefas Assíncronas:** Celery + Redis
- **Armazenamento:** AWS S3
- **Integrações:** FedHub (e-mails/notificações), API de NFS-e, BigDataCorp (consulta de CNPJ)
- **Container:** Docker + Gunicorn

## Estrutura do Projeto

```
VR-BCK/
├── core/                  # Configurações Django (settings, urls, wsgi, asgi, celery)
│   ├── schema.py          # AutoSchema customizado do OpenAPI (tags e fallbacks)
│   └── fedhub/            # Cliente da integração FedHub
├── users/                 # Autenticação, usuários e vínculo com administradoras
├── entidades/             # Administradoras, condomínios, funcionários, gerentes,
│                          # vínculos e configurações de taxa
├── beneficios/            # Produtos, movimentações, importações, boletos,
│                          # kanban e pedidos de cartão
├── upload/                # Upload e parsing de planilhas, faturamento, exports
│   ├── EXCEL/             # Parsers e templates das planilhas VR
│   ├── RB/ AHREAS/        # Parsers dos layouts TXT
│   ├── vt_upload.py       # Fluxo de vale transporte
│   ├── tasks.py           # Tarefas Celery
│   ├── pdf_reader.py      # Leitura de PDFs de boleto / nota de débito
│   ├── nfse_service.py    # Emissão de NFS-e
│   └── views_nfse.py      # Webhook de retorno da NFS-e
├── consultas/             # Consultas externas (CNPJ, Google Auth)
├── manage.py
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## Documentação interativa (Swagger)

O schema OpenAPI 3 é gerado automaticamente a partir das views e serializers.

| Rota | Descrição |
|------|-----------|
| `GET /api/docs/` | Swagger UI (interativo, com "Authorize" para o token JWT) |
| `GET /api/redoc/` | ReDoc (leitura) |
| `GET /api/schema/` | Schema OpenAPI 3 em YAML |

As rotas de documentação são públicas (`AllowAny`); os endpoints em si continuam exigindo autenticação.

**Como testar autenticado no Swagger UI:**

1. Chame `POST /api/auth/token/` (ou `POST /api/users/login/`) com e-mail e senha.
2. Copie o valor de `access`.
3. Clique em **Authorize** e informe `Bearer <access>`.

**Gerar o schema em arquivo:**

```bash
python manage.py spectacular --file schema.yml
```

### Documentando novos endpoints

Boa parte da API usa `APIView` pura, sem `serializer_class`. Para que esses
endpoints não fiquem de fora da documentação, `core/schema.py` define o
`VRAutoSchema`, que:

- agrupa as operações em tags de negócio a partir do prefixo da URL;
- aplica um corpo/resposta genérico (objeto JSON livre) como fallback.

Para descrever o contrato real de um endpoint, anote a view — a anotação sempre
tem prioridade sobre o fallback:

```python
from drf_spectacular.utils import extend_schema

class MinhaView(views.APIView):
    @extend_schema(request=MeuSerializer, responses=MeuResponseSerializer)
    def post(self, request):
        ...
```

---

## Configuração

### Variáveis de Ambiente (.env)

```env
# Django
SECRET_KEY=sua_chave_secreta
DEBUG=False
FRONTEND_URL=http://localhost:5173

# Banco
DB_USER=seu_usuario
DB_PASSWORD=sua_senha
DB_HOST=seu_host
DB_PORT=5432
DB_NAME=nome_banco

# AWS S3
ACCESS_KEY_S3=sua_access_key
SECRET_KEY_S3=sua_secret_key
BUCKET_S3=nome_do_bucket

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# FedHub (e-mails e notificações)
FEDHUB_URL=http://localhost:8090
FEDHUB_X_API_KEY=
# Bearer token renovável (novo modelo de auth; a chave acima segue como fallback)
FEDHUB_CLIENT_ID=
FEDHUB_CLIENT_SECRET=
EMAIL_FATURAMENTO=faturamento@fedcorp.com

# NFS-e
NFSE_API_URL=
NFSE_PRESTADOR_CPF_CNPJ=
NFSE_PRESTADOR_RAZAO_SOCIAL=
NFSE_SERVICO_CODIGO=
NFSE_TOMADOR_CODIGO_PADRAO=
NFSE_X_API_KEY=

# Consulta de CNPJ (BigDataCorp)
BIGDATA_URL=https://plataforma.bigdatacorp.com.br/empresas
BIGDATA_ACCESS_TOKEN=
BIGDATA_TOKEN_ID=
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

## Fluxos de Trabalho

### 1. Upload de Movimentações VR/VA

Aceita planilhas `.xlsx`/`.xlsm` (template VR) e arquivos `.txt` nos layouts **RB** e **AHREAS** — o layout é detectado automaticamente.

1. `POST /api/upload/` com o arquivo e a administradora
2. O backend faz o parsing e devolve um resumo (condomínios, funcionários, movimentações, taxas e linhas com erro) **sem gravar nada**
3. O front revisa/corrige e chama `POST /api/upload/confirm/`
4. São criados/atualizados condomínios, funcionários, produtos, movimentações e a `Importacao`
5. Em background, os endereços dos condomínios são complementados por consulta de CNPJ

**Payload de confirmação:**

```json
{
    "file_upload_id": 1,
    "condominios": [...],
    "data_vencimento": "2026-04-10",
    "vigencia_inicio": "2026-04-01",
    "vigencia_fim": "2026-04-30"
}
```

### 2. Upload de Vale Transporte (VT)

Mesmo modelo em duas etapas, com parser e template próprios:

- `POST /api/upload/vt/` — envia e interpreta a planilha VT
- `POST /api/upload/vt/confirm/` — confirma e grava
- `GET /api/upload/export/vt-compra/` — gera o arquivo de compra VT

### 3. Importação da Base de Condomínios

Cadastro em massa de condomínios e funcionários, **sem** gerar faturamento:

- `POST /api/beneficios/importar-base/` — Excel via `multipart/form-data`
- `DELETE /api/beneficios/excluir-base/<administradora_id>/` — remove a base da administradora

### 4. Faturamento (PDF - Assíncrono)

Upload de boleto, nota de débito e nota fiscal com processamento em background via Celery.

**Fluxo:**
1. Frontend envia os PDFs
2. Backend cria/atualiza o registro `Faturamento` (mesmo ID da importação)
3. A task Celery lê os PDFs, extrai os CNPJs, separa as páginas por condomínio, envia cada arquivo ao S3 e grava os documentos
4. Frontend faz polling no endpoint de status

**Regras:**
- `importacao_id` = `faturamento_id` (mesmo valor)
- Se já existir faturamento para a importação, o anterior é apagado e um novo é criado

**Status possíveis:** `PENDING`, `PROCESSING` (com `progresso` de 0 a 100), `COMPLETED`, `FAILED`

**Resposta de status:**
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

### 5. NFS-e e Boletos

- A emissão de NFS-e é feita pelo serviço externo configurado em `NFSE_API_URL`
- O retorno chega em `POST /api/upload/nfse/webhook/`, autenticado pelo header `X-API-KEY`
- O `id_integracao` segue o formato `VR_{faturamento_id}_{cnpj_condominio}`
- Baixa de boletos: `POST|PATCH /api/beneficios/boletos/baixa/` (por identificador no corpo) ou `/api/beneficios/boletos/<id>/baixa/`

### 6. Kanban Operacional

Acompanhamento das faturas e boletos por coluna de status:

- `GET /api/beneficios/kanban/faturas/` — agrupa `Importacao` + `Faturamento` + `Boletos`
- `GET /api/beneficios/kanban/boletos/`
- `PATCH /api/beneficios/kanban/<id>/move/` — body: `{ "status": "faturado" | "atrasado" | "aprovado" | "pago" }`
- `GET /api/beneficios/kanban/notificar-compra/` — dispara e-mail para faturas com crédito no dia seguinte

### 7. Pedidos de Cartão

- `POST|GET /api/beneficios/pedidos-cartao/` — cria/lista pedidos da administradora do usuário logado
- `GET /api/beneficios/pedidos-cartao/operacional/` — visão do time operacional
- `PATCH /api/beneficios/pedidos-cartao/<id>/status/`

Tipos: `NOVO`, `SEGUNDA_VIA`. Status: `PENDENTE`, `EM_ANALISE`, `APROVADO`, `ENVIADO`.

---

## Configuração de Taxas

A taxa de faturamento é resolvida por vínculo (administradora + condomínio), na seguinte ordem de prioridade:

1. `TaxaConfig` do **produto** específico
2. `TaxaConfig` do **tipo** de produto
3. `TaxaConfig` **genérica** do vínculo (`produto` e `tipo` nulos)
4. Taxa padrão da administradora (`taxa_padrao_tipo` / `taxa_padrao_valor`)

Tipos de taxa:
- `PERC` — percentual: `valor_beneficio * (taxa_valor / 100)`
- `FIXO` — valor fixo: `taxa_valor * quantidade_dias`

Endpoints: `/api/entidades/taxas-config/` (CRUD). As taxas de um vínculo também vêm embutidas em `/api/entidades/vinculos/` no campo `taxas_config`.

Regras de permissão: usuários `dev` e `fat` gerenciam qualquer taxa; usuários `adm` só gerenciam taxas da administradora ativa.

---

## API Endpoints

Autenticação por JWT no header `Authorization: Bearer <access>`, salvo onde indicado.

### Autenticação
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/auth/token/` | Obter token de acesso |
| POST | `/api/auth/token/refresh/` | Renovar token |
| POST | `/api/auth/token/verify/` | Verificar token |

### Usuários
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/users/login/` | Login |
| POST | `/api/users/refresh/` | Renovar token |
| POST | `/api/users/register/` | Registrar usuário |
| POST | `/api/users/google-login/` | Login via Google |
| GET / PUT / PATCH | `/api/users/me/` | Usuário atual |
| POST | `/api/users/password/` | Alterar senha |
| POST | `/api/users/set-administradora-ativa/` | Definir administradora ativa |
| GET | `/api/users/list/` | Listar usuários |
| GET / PUT / PATCH / DELETE | `/api/users/<id>/` | Detalhe do usuário |
| POST | `/api/users/<id>/vincular-adm/` | Vincular administradora |
| POST | `/api/users/<id>/desvincular-adm/` | Desvincular administradora |
| POST | `/api/users/reenviar-email-boas-vindas/` | Reenviar e-mail de boas-vindas |
| POST | `/api/users/solicitar-reset-senha/` | Solicitar reset de senha |
| GET | `/api/users/validar-token-reset/<token>/` | Validar token de reset |
| POST | `/api/users/resetar-senha/` | Concluir reset de senha |

### Entidades
| Método | Rota | Descrição |
|--------|------|-----------|
| GET / POST | `/api/entidades/administradoras/` | Administradoras (`?ativo=true`) |
| GET / PUT / PATCH / DELETE | `/api/entidades/administradoras/<id>/` | Detalhe |
| GET | `/api/entidades/administradoras/<id>/condominios/` | Condomínios da administradora |
| GET / POST | `/api/entidades/administradoras/<id>/regra-valor/` | Regra de valor |
| PUT | `/api/entidades/administradoras/<id>/regra-valor/<regra_id>/` | Atualizar regra de valor |
| GET / POST | `/api/entidades/condominios/` | Condomínios (chave: CNPJ) |
| GET / PUT / PATCH / DELETE | `/api/entidades/condominios/<cnpj>/` | Detalhe |
| GET / POST | `/api/entidades/funcionarios/` | Funcionários (chave: CPF) |
| GET / PUT / PATCH / DELETE | `/api/entidades/funcionarios/<cpf>/` | Detalhe |
| GET / POST | `/api/entidades/gerentes/` | Gerentes |
| GET / PUT / PATCH / DELETE | `/api/entidades/gerentes/<id>/` | Detalhe |
| GET / POST | `/api/entidades/vinculos/` | Vínculos administradora ↔ condomínio |
| GET / PUT / PATCH / DELETE | `/api/entidades/vinculos/<id>/` | Detalhe |
| GET / POST | `/api/entidades/taxas-config/` | Configurações de taxa |
| GET / PUT / PATCH / DELETE | `/api/entidades/taxas-config/<id>/` | Detalhe |

Filtros disponíveis em `taxas-config`: `?vinculo=`, `?administradora=`, `?condominio=<cnpj>`, `?produto=<codigo>`, `?tipo=`, `?ativo=`.

### Benefícios
| Método | Rota | Descrição |
|--------|------|-----------|
| GET / POST | `/api/beneficios/produtos/` | Catálogo de produtos |
| GET / PUT / PATCH / DELETE | `/api/beneficios/produtos/<codigo_produto>/` | Detalhe |
| GET / POST | `/api/beneficios/movimentacoes/` | Movimentações |
| GET / PUT / PATCH / DELETE | `/api/beneficios/movimentacoes/<id>/` | Detalhe |
| GET | `/api/beneficios/importacoes/` | Histórico de importações (`?page=&limit=`) |
| GET | `/api/beneficios/importacoes/<id>/` | Detalhe (`?mov_page=&mov_limit=`) |
| GET | `/api/beneficios/importacoes/ultima/` | Última importação |
| GET | `/api/beneficios/importacoes/ultima-movimentacao/` | Dados para o dashboard |
| PATCH | `/api/beneficios/importacoes/<id>/status/` | Alterar status |
| PATCH | `/api/beneficios/importacoes/<id>/responsavel/` | Marcar responsável |
| POST | `/api/beneficios/importacoes/<id>/reenviar-email/` | Reenviar e-mail |
| GET | `/api/beneficios/boletos/` | Listar boletos |
| POST / PATCH | `/api/beneficios/boletos/baixa/` | Baixa por identificador/documento |
| POST / PATCH | `/api/beneficios/boletos/<id>/baixa/` | Baixa por ID |
| GET | `/api/beneficios/consulta-boletos/` | Consulta de boletos |
| GET | `/api/beneficios/kanban/faturas/` | Kanban de faturas |
| GET | `/api/beneficios/kanban/boletos/` | Kanban de boletos |
| PATCH | `/api/beneficios/kanban/<id>/move/` | Mover fatura de coluna |
| GET | `/api/beneficios/kanban/notificar-compra/` | Notificar compras do dia seguinte |
| POST | `/api/beneficios/importar-base/` | Importar base de condomínios |
| DELETE | `/api/beneficios/excluir-base/<administradora_id>/` | Excluir base |
| GET / POST | `/api/beneficios/pedidos-cartao/` | Pedidos de cartão |
| GET | `/api/beneficios/pedidos-cartao/operacional/` | Visão operacional |
| PATCH | `/api/beneficios/pedidos-cartao/<id>/status/` | Alterar status do pedido |

### Upload
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/upload/` | Upload VR/VA (Excel ou TXT) |
| POST | `/api/upload/confirm/` | Confirmar dados processados |
| POST | `/api/upload/vt/` | Upload VT |
| POST | `/api/upload/vt/confirm/` | Confirmar dados VT |
| GET | `/api/upload/download-excel-vr/` | Baixar template VR |
| GET | `/api/upload/download-excel-vt/` | Baixar template VT |
| POST | `/api/upload/export/txt-compra/` | Gerar TXT de compra (VR) |
| GET | `/api/upload/export/vt-compra/` | Gerar arquivo de compra (VT) |
| GET | `/api/upload/export/faturamento/` | Exportar planilha de faturamento |
| POST | `/api/upload/faturamento/upload/` | Upload de faturamento (assíncrono) |
| GET | `/api/upload/faturamento/<id>/status/` | Status do faturamento |
| GET | `/api/upload/importacao/<id>/download/` | Baixar arquivo da importação |
| GET | `/api/upload/importacao/<id>/select-data/` | Dados auxiliares de seleção |
| GET | `/api/upload/boletos/` | Listar todos os boletos |
| POST | `/api/upload/nfse/webhook/` | Webhook de NFS-e (header `X-API-KEY`) |

**Downloads de faturamento** (todos sob `/api/upload/faturamento/<id>/download/`):

| Rota | Conteúdo |
|------|----------|
| `/` | Todos os documentos |
| `boletos/` | Boletos separados por condomínio |
| `notas-debito/` | Notas de débito separadas |
| `notas-fiscais/` | Notas fiscais separadas |
| `notas-emitidas/` | Notas emitidas via NFS-e |
| `boleto-original/` | PDF original do boleto |
| `nota-debito-original/` | PDF original da nota de débito |
| `nota-fiscal-original/` | PDF original da nota fiscal |
| `originais/` | Todos os PDFs originais |

### Consultas
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/consultas/administradoras/` | Buscar administradoras |
| GET | `/api/consultas/administradoras/por-cnpj/<cnpj>/` | Buscar administradora por CNPJ |
| GET | `/api/consultas/pessoas/por-cnpj/<cnpj>/` | Buscar sócios/pessoas por CNPJ |
| POST | `/api/consultas/recuperar-google-auth/` | Recuperar autenticação Google |

---

## Modelos

### TaxaConfig (entidades)
- `vinculo`: FK para VinculoCondominio
- `produto`: FK para Produto (opcional — vazio aplica a todos)
- `tipo`: tipo de produto (opcional — alternativa ao produto)
- `taxa_tipo`: `PERC` ou `FIXO`
- `taxa_valor`: valor da taxa
- `ativo`: booleano

Restrições de unicidade: uma taxa por vínculo+produto, uma por vínculo+tipo e uma genérica por vínculo.

### Importacao (beneficios)
- `id`: ID único (também usado como `faturamento_id`)
- `file_upload`: FK para FileUpload
- `usuario`: FK para usuário
- `data_importacao`: Data/hora da importação
- `status`: PENDING/PROCESSING/COMPLETED/FAILED
- `total_registros`, `registros_processados`, `erros`
- `url`: URL do arquivo processado
- `data_vencimento`, `vigencia_inicio`, `vigencia_fim`

### Faturamento (beneficios)
- `id`: ID único (mesmo que `importacao_id`)
- `importacao`: FK para Importacao
- `competencia`: Data (YYYY-MM-DD)
- `status`: PENDING/PROCESSING/COMPLETED/FAILED
- `progresso`: Inteiro 0-100
- `criado_por`, `criado_em`

### FaturamentoDocumento (beneficios)
- `faturamento`: FK para Faturamento
- `condominio`: FK para Condomínio
- `url_boleto`, `url_nota_debito`, `url_nota_fiscal`: URLs no S3

### FaturamentoArquivo (beneficios)
- Guarda os PDFs originais enviados
- `tipo`: `boleto`, `nota_debito` ou `nota_fiscal`
- `fatura_num`, `nome_arquivo`, `s3_key`, `url`

### PedidoCartao (beneficios)
- `tipo`: `NOVO` ou `SEGUNDA_VIA`
- `status`: `PENDENTE`, `EM_ANALISE`, `APROVADO`, `ENVIADO`

---

## Processamento de Planilhas e PDF

### Planilhas
- **Template VR** (`.xlsx`/`.xlsm`): abas `Local de Entrega` e `Beneficiário`
- **Layouts TXT**: `RB` e `AHREAS`, detectados automaticamente
- Quando há apenas um local de entrega, a importação assume modo **cartão admin** (entrega centralizada na administradora)

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

## Migrações

```bash
# Criar migrações
python manage.py makemigrations

# Aplicar migrações
python manage.py migrate
```

---

## Licença

Proprietário - FedCorp
