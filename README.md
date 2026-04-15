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
- `GET /api/users/` - Listar usuários
- `POST /api/users/` - Criar usuário
- `GET /api/users/{id}/` - Detalhes do usuário

### Entidades
- `GET /api/entidades/administradoras/` - Listar administradoras
- `GET /api/entidades/condominios/` - Listar condomínios
- `GET /api/entidades/funcionarios/` - Listar funcionários
- `GET /api/entidades/gerentes/` - Listar gerentes
- `GET /api/entidades/vinculos/` - Listar vínculos

### Benefícios
- `GET /api/beneficios/produtos/` - Listar produtos
- `GET /api/beneficios/movimentacoes/` - Listar movimentações

### Upload
- `POST /api/upload/` - Upload de arquivo Excel
- `POST /api/upload/confirm/` - Confirmar dados processados
- `GET /api/upload/list-confirmed/` - Listar confirmações
- `GET /api/upload/download-excel-template/` - Baixar template Excel
- `GET /api/upload/export/txt-compra/` - Exportar TXT de compra
- `GET /api/upload/export/faturamento/` - Exportar planilha faturamento

## Requisitos

- Python 3.10+
- PostgreSQL 12+
- Docker (opcional)

## Licença

Proprietário - FedCorp