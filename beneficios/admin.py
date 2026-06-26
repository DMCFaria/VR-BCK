from django.contrib import admin
from .models import Produto, MovimentacaoBeneficio, Importacao, NotaFiscal

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('codigo_produto', 'nome')
    search_fields = ('codigo_produto', 'nome')

@admin.register(MovimentacaoBeneficio)
class MovimentacaoBeneficioAdmin(admin.ModelAdmin):
    list_display = ('id', 'empresa_cnpj', 'funcionario_cpf', 'produto_codigo', 'data_competencia', 'valor_beneficio', 'importacao')
    list_filter = ('data_competencia', 'importacao')
    search_fields = ('empresa_cnpj__cnpj', 'funcionario_cpf__cpf')

@admin.register(Importacao)
class ImportacaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'file_upload', 'usuario', 'data_importacao', 'status', 'total_registros', 'registros_processados')
    list_filter = ('status', 'data_importacao')

@admin.register(NotaFiscal)
class NotaFiscalAdmin(admin.ModelAdmin):
    list_display = ('id', 'faturamento', 'condominio', 'id_integracao', 'status', 'numero_nota', 'created_at')
    list_filter = ('status',)
    search_fields = ('id_integracao', 'numero_nota', 'condominio__cnpj')
