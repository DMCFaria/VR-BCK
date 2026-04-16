# VR-BCK - Backend de Gestão de Benefícios

API REST para gestão de benefícios de funcionários (Vale Refeição).

## Tecnologias

- **Framework:** Django 5.2 + Django REST Framework
- **Autenticação:** JWT (Simple JWT)
- **Banco de Dados:** PostgreSQL
- **Processamento:** Pandas, NumPy (manipulação de arquivos Excel)
- **Container:** Docker + Gunicorn

## Estrutura do Projeto

```
VR-BCK/
├── core/           # Configurações Django (settings, urls, wsgi, asgi)
├── users/         # Autenticação e gestão de usuários
├── entidades/     # Cadastro de administradoras, condomínios e funcionários
├── beneficios/   # Catálogo de produtos e movimentações
├── upload/        # Upload, processamento de Excel e exports
├── manage.py
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Modelos

### Users
- **CustomUser:** Usuário com tipos (Desenvolvedor, Financeiro, Faturista, Administrador, Cliente), linked to Administradora

### Entidades
- **Administradora:** Empresas administradoras de benefícios (CNPJ como chave)
- **Gerente:** Gerentes responsáveis por vínculos
- **VinculoCondominio:** Relacionamento N:N entre Administradora, Condomínio e Gerentes
- **Condominio:** Entidade principal (CNPJ como chave)
- **Funcionario:** Cadastro de funcionários (CPF como chave)

### Benefícios
- **Produto:** Catálogo de benefícios
- **MovimentacaoBeneficio:** Registro de transações (unique por competência)

### Upload
- **FileUpload:** Arquivos enviados com status (PENDING → PARSED → COMPLETED)
- **ProcessedFile:** Rastreamento de processamentos confirmados

## Configuração

### Variáveis de Ambiente (.env)

```env
DB_USER=seu_usuario
DB_PASSWORD=sua_senha
DB_HOST=seu_host
DB_PORT=sua_porta
DB_NAME=nome_banco
SECRET_KEY=sua_chave_secreta
```

### Instalação

```bash
python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Docker

```bash
docker-compose up --build
```

## API Endpoints

### Autenticação
- `POST /api/auth/token/` - Obter token de acesso
- `POST /api/auth/token/refresh/` - Renovar token
- `POST /api/auth/token/verify/` - Verificar token

### Usuários
- `POST /api/users/login/` - Login de usuário
- `POST /api/users/register/` - Registrar usuário
- `GET /api/users/me/` - Usuário atual
- `GET /api/users/list/` - Listar usuários (requer autenticação)
- `GET/PUT/DELETE /api/users/{id}/` - Detalhes do usuário

### Entidades
- `GET /api/entidades/administradoras/` - Listar/Criar administradoras
- `GET/PUT/DELETE /api/entidades/administradoras/{id}/` - Detalhe da administradora
- `GET /api/entidades/condominios/` - Listar/Criar condomínios
- `GET/PUT/DELETE /api/entidades/condominios/{cnpj}/` - Detalhe do condomínio
- `GET /api/entidades/funcionarios/` - Listar/Criar funcionários
- `GET/PUT/DELETE /api/entidades/funcionarios/{cpf}/` - Detalhe do funcionário
- `GET /api/entidades/gerentes/` - Listar/Criar gerentes
- `GET/PUT/DELETE /api/entidades/gerentes/{id}/` - Detalhe do gerente
- `GET /api/entidades/vinculos/` - Listar/Criar vínculos
- `GET/PUT/DELETE /api/entidades/vinculos/{id}/` - Detalhe do vínculo

### Benefícios
- `GET /api/beneficios/produtos/` - Listar/Criar produtos
- `GET/PUT/DELETE /api/beneficios/produtos/{codigo}/` - Detalhe do produto
- `GET /api/beneficios/movimentacoes/` - Listar/Criar movimentações
- `GET/PUT/DELETE /api/beneficios/movimentacoes/{id}/` - Detalhe da movimentação

### Upload
- `POST /api/upload/` - Upload de arquivo Excel
- `POST /api/upload/confirm/` - Confirmar dados processados
- `GET /api/upload/list-confirmed/` - Listar confirmações
- `GET /api/upload/download-excel-template/` - Baixar template Excel
- `POST /api/upload/export/txt-compra/` - Exportar TXT de compra
- `GET /api/upload/export/faturamento/` - Exportar planilha faturamento

## Payload de Confirmação (upload/confirm/)

O endpoint `/api/upload/confirm/` espera o seguinte formato de payload:

```json
{
    "file_upload_id": 100,
    "condominios": [
        {
            "nome": "CONDOMINIO EDIFICIO X",
            "cnpj": "0346804400013",
            "valor_condo": "3473.13",
            "funcionarios": [
                {
                    "nome": "NOME DO FUNCIONÁRIO",
                    "cpf": "71823131468",
                    "matricula": "9000200000900",
                    "departamento": "CONDOMINIO",
                    "funcao": "ZELADOR",
                    "data_nascimento": "1970-08-17",
                    "valor_bene": "569.98",
                    "movimentacoes": [
                        {
                            "produto": "VALE REFEICAO - TICKET",
                            "valor": "17.9"
                        },
                        {
                            "produto": "VALE ALIMENTACAO - TICKET",
                            "valor": "552.08"
                        }
                    ]
                }
            ]
        }
    ]
}
```

### Validações do Payload
- `file_upload_id`: Obrigatório - ID do arquivo enviado
- `condominios`: Lista obrigatória - ao menos um condomínio
- `cnpj`: Obrigatório e único
- `cpf`: Obrigatório e único por funcionário
- `data_nascimento`: Opcional - datas inválidas são ignoradas
- `data_competencia`: Se não informada, usa a primeira data_nascimento válida ou data atual

### Datas Inválidas Tratadas
As seguintes datas são automaticamente convertidas para `null`:
- `0000-00-00`
- `0001-01-01`
- `0020-00-00`
- `1900-01-01`

## Requisitos

- Python 3.10+
- PostgreSQL 12+
- Docker (opcional)

## Testes

```bash
python manage.py test
```

## Licença

Proprietário - FedCorp
