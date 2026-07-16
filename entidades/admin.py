from django.contrib import admin
from .models import Condominio, Funcionario, Administradora, VinculoCondominio, Gerente, TaxaConfig


@admin.register(Administradora)
class AdministradoraAdmin(admin.ModelAdmin):
    list_display = ['cnpj', 'razao_social', 'ativo', 'd_mais', 'created_at']
    list_filter = ['ativo']
    search_fields = ['cnpj', 'razao_social']
    ordering = ['razao_social']


@admin.register(Gerente)
class GerenteAdmin(admin.ModelAdmin):
    list_display = ['nome', 'email', 'telefone', 'ativo', 'created_at']
    list_filter = ['ativo']
    search_fields = ['nome', 'email']
    ordering = ['nome']


class TaxaConfigInline(admin.TabularInline):
    model = TaxaConfig
    extra = 1
    fields = ['produto', 'taxa_tipo', 'taxa_valor', 'ativo']
    verbose_name = "Configuração de Taxa"
    verbose_name_plural = "Configurações de Taxas"


@admin.register(VinculoCondominio)
class VinculoCondominioAdmin(admin.ModelAdmin):
    list_display = ['administradora', 'condominio', 'created_at']
    list_filter = ['administradora']
    search_fields = ['condominio__nome', 'condominio__cnpj', 'administradora__razao_social']
    filter_horizontal = ['gerentes']
    inlines = [TaxaConfigInline]


@admin.register(Condominio)
class CondominioAdmin(admin.ModelAdmin):
    list_display = ['cnpj', 'nome', 'cidade', 'estado']
    list_filter = ['estado', 'cidade']
    search_fields = ['cnpj', 'nome']
    ordering = ['nome']


@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ['cpf', 'nome', 'matricula', 'departamento']
    list_filter = ['departamento']
    search_fields = ['cpf', 'nome', 'matricula']
    ordering = ['nome']


@admin.register(TaxaConfig)
class TaxaConfigAdmin(admin.ModelAdmin):
    list_display = ['vinculo', 'produto', 'taxa_tipo', 'taxa_valor', 'ativo', 'created_at']
    list_filter = ['ativo', 'taxa_tipo', 'vinculo__administradora']
    search_fields = [
        'vinculo__condominio__nome', 
        'vinculo__condominio__cnpj',
        'vinculo__administradora__razao_social',
        'produto__nome',
        'produto__codigo_produto'
    ]
    list_editable = ['ativo', 'taxa_tipo', 'taxa_valor']
    ordering = ['-created_at']
