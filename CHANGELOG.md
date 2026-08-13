## [11/08/2026]
[CORREÇÃO] Detecção de cartão admin no parser VR (`upload/EXCEL/reader2.py`): além do caso de 1 único local de entrega, planilhas com vários locais que repetem o MESMO endereço (o da administradora) agora também são tratadas como cartão admin. Antes, esse formato híbrido gravava o endereço da administradora em todos os condomínios e a planilha de faturamento saía com endereço errado (caso Praiamar / importação 319).

## [20/04/2026]
[NOVIDADE] Adicionada capacidade de importar e salvar o endereço completo dos condomínios (rua, número, bairro, cidade, estado, CEP) a partir dos uploads de arquivos Excel e RB.
[NOVIDADE] Novos arquivos enviados são automaticamente arquivados no S3 com nomes padronizados para melhor organização e rastreabilidade.

