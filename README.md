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
├── users/          # Autenticação e gestão de usuários
├── entidades/      # Cadastro de condomínios e funcionários
├── beneficios/     # Catálogo de produtos e movimentações
├── upload/         # Upload e processamento de arquivos Excel
├── docs/           # Documentação
├── manage.py
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Apps

### Users
- Modelo CustomUser com tipos: Desenvolvedor, Financeiro, Faturista, Administrador, Cliente
- Autenticação via JWT com refresh tokens

### Entidades
- **Condominio:** Entidade principal (CNPJ como chave)
- **Funcionario:** Cadastro de funcionários (CPF como chave)

### Benefícios
- **Produto:** Catálogo de benefícios
- **MovimentacaoBeneficio:** Registro de transações (evita duplicidade por competência)

### Upload
- Upload de arquivos Excel
- Pipeline de processamento: PENDING → PARSED → COMPLETED
- Rastreamento de arquivos processados

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
# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Instalar dependências
pip install -r requirements.txt

# Executar migrations
python manage.py migrate

# Criar superusuário
python manage.py createsuperuser

# Executar servidor
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
- `GET /api/users/` - Listar usuários
- `POST /api/users/` - Criar usuário
- `GET /api/users/{id}/` - Detalhes do usuário

### Entidades
- `GET /api/entidades/condominios/` - Listar condomínios
- `GET /api/entidades/funcionarios/` - Listar funcionários

### Benefícios
- `GET /api/beneficios/produtos/` - Listar produtos
- `GET /api/beneficios/movimentacoes/` - Listar movimentações

### Upload
- `POST /api/upload/` - Upload de arquivo Excel
- `GET /api/upload/files/` - Listar uploads
- `GET /api/upload/processed/` - Listar arquivos processados

## Requisitos

- Python 3.10+
- PostgreSQL 12+
- Docker (opcional)

## Licença

Proprietário - FedCorp
