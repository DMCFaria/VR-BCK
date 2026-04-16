# Checklist de Boas Práticas para Produção

## 1. SEGURANÇA

### Configurações Críticas
- [ ] `DEBUG = False` em produção (settings.py:10 - atualmente True)
- [ ] `ALLOWED_HOSTS` - remover localhost/127.0.0.1 em produção
- [ ] `SECRET_KEY` via variável de ambiente, não hardcoded
- [ ] `SIMPLE_JWT.SIGNING_KEY` diferente da SECRET_KEY

### CORS
- [ ] `CORS_ALLOWED_ORIGINS` - domínios específicos do frontend em produção

### Validação
- [ ] Implementar validação de CPF (módulo 11)
- [ ] Implementar validação de CNPJ (módulo 11)
- [ ] Adicionar rate limiting para endpoints sensíveis

---

## 2. PERFORMANCE

### Banco de Dados
- [ ] Adicionar índices em ForeignKeys frequentemente consultados
- [ ] Adicionar índice em `MovimentacaoBeneficio.data_competencia`
- [ ] Implementar paginação em todos os endpoints de listagem
- [ ] Considerar partição de tabelas por data

### Queries
- [ ] `serializers.py:204-205` - Loop N+1 nos vínculos (usar bulk_create)
- [ ] ViewSets - adicionar `select_related`/`prefetch_related`

---

## 3. TRATAMENTO DE ERROS

### Serializers
- [ ] `serializers.py:212` - Validar CNPJ inexistente após bulk_create
- [ ] `serializers.py:247` - transaction.atomic() deve envolver toda operação

### Views
- [ ] `confirmed.py:59` - Tratar exceções específicas (não Exception genérico)
- [ ] `export.py:116` - Tratar `timedelta(days=30)` para meses curtos
- [ ] `export.py:217` - Tratar DataFrame vazio no XLSX

### Logging
- [ ] Configurar logging estruturado (JSON)
- [ ] Registrar erros com contexto (user_id, file_upload_id)

---

## 4. VALIDAÇÃO DE DADOS

### Datas
- [ ] `export.py:116` - Usar `relativedelta` para cálculo de meses
- [ ] Validar range de datas (não permitir competência futura)

### Valores
- [ ] Validar que valores monetários não são negativos
- [ ] Validar precisão decimal (máximo 2 casas)

---

## 5. INFRAESTRUTURA

### Configurações
- [ ] Separar settings em base/production/local
- [ ] Configurar health check endpoint
- [ ] Implementar métricas (Prometheus/StatsD)

### Arquivos
- [ ] Storage S3/Cloud para uploads (atualmente local)
- [ ] Definir limites de tamanho de arquivo
- [ ] Limpeza automática de arquivos temporários

### Backup
- [ ] Backup automático do banco
- [ ] Testar procedimentos de recovery

---

## 6. MONITORAMENTO

- [ ] Agregação de logs (ELK, Datadog)
- [ ] Alertas para erros 5xx
- [ ] Monitoramento de latência de API

---

## 7. TESTES

### Cobertura
- [ ] Tests para serializers (validação)
- [ ] Tests de integração (end-to-end)
- [ ] Tests de performance (load testing)

### Cenários
- [ ] Payload vazio/inválido
- [ ] Payload grande (stress test)
- [ ] Perda de conexão durante transação

---

## 8. DOCUMENTAÇÃO

- [ ] OpenAPI/Swagger para todos endpoints
- [ ] Documentar formatos de erro
- [ ] Exemplos de requisição/resposta
