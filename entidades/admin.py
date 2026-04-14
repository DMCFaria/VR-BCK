from django.contrib import admin
from .models import Condominio, Funcionario, Administradora, VinculoCondominio, Gerente


@admin.register(Administradora)
class AdministradoraAdmin(admin.ModelAdmin):
    list_display = ['cnpj', 'nome', 'ativo', 'created_at']
    list_filter = ['ativo']
    search_fields = ['cnpj', 'nome']
    ordering = ['nome']


@admin.register(Gerente)
class GerenteAdmin(admin.ModelAdmin):
    list_display = ['nome', 'email', 'telefone', 'ativo', 'created_at']
    list_filter = ['ativo']
    search_fields = ['nome', 'email']
    ordering = ['nome']


@admin.register(VinculoCondominio)
class VinculoCondominioAdmin(admin.ModelAdmin):
    list_display = ['administradora', 'condominio', 'created_at']
    list_filter = ['administradora']
    search_fields = ['condominio__nome', 'condominio__cnpj', 'administradora__nome']
    filter_horizontal = ['gerentes']


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
