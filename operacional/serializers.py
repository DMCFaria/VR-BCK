from rest_framework import serializers
from .models import Fatura, CoEstipulante, Boleto, FaturaComment


class CoEstipulanteSerializer(serializers.ModelSerializer):
    idx = serializers.SerializerMethodField()

    class Meta:
        model = CoEstipulante
        fields = [
            'id', 'idx', 'nome', 'cnpj', 'valor_cents', 'due_date',
            'data_credito', 'paid_at', 'sent_to_cp', 'forma_pagamento',
        ]

    def get_idx(self, obj):
        return obj.id

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update({
            'name': instance.nome,
            'cpf_cnpj': instance.cnpj,
            'cpfCnpj': instance.cnpj,
            'documento': instance.cnpj,
            'valorCents': instance.valor_cents,
            'valorCentavos': instance.valor_cents,
            'valor_total': instance.valor_cents,
            'valor': instance.valor_cents,
            'total': instance.valor_cents,
            'dueDate': instance.due_date.isoformat() if instance.due_date else None,
            'due_date': instance.due_date.isoformat() if instance.due_date else None,
            'vencimento': instance.due_date.isoformat() if instance.due_date else None,
            'data_vencimento': instance.due_date.isoformat() if instance.due_date else None,
            'dt_vencimento': instance.due_date.isoformat() if instance.due_date else None,
            'dataCredito': instance.data_credito.isoformat() if instance.data_credito else None,
            'data_credito': instance.data_credito.isoformat() if instance.data_credito else None,
            'credito': instance.data_credito.isoformat() if instance.data_credito else None,
            'paidAt': instance.paid_at.isoformat() if instance.paid_at else None,
            'paid_at': instance.paid_at.isoformat() if instance.paid_at else None,
            'data_pagamento': instance.paid_at.isoformat() if instance.paid_at else None,
            'pago_em': instance.paid_at.isoformat() if instance.paid_at else None,
            'dt_pagamento': instance.paid_at.isoformat() if instance.paid_at else None,
            'sentToCP': instance.sent_to_cp,
            'sent_to_cp': instance.sent_to_cp,
            'enviado_cp': instance.sent_to_cp,
            'enviado_contas_pagar': instance.sent_to_cp,
            'enviadoContasPagar': instance.sent_to_cp,
            'formaPagemento': instance.forma_pagamento,
            'formaPagamento': instance.forma_pagamento,
        })
        return data


class FaturaSerializer(serializers.ModelSerializer):
    co_estipulantes = CoEstipulanteSerializer(many=True, read_only=True)

    class Meta:
        model = Fatura
        fields = [
            'id', 'fatura_num', 'emissao', 'estipulante_nome', 'estipulante_cnpj',
            'administradora_nome', 'uploader_name', 'uploader', 'manual_status',
            'total_cents', 'arquivo_pdf', 'created_at', 'updated_at',
            'co_estipulantes',
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = instance.uploader
        data.update({
            'faturaNum': instance.fatura_num,
            'numero_fatura': instance.fatura_num,
            'numero': instance.fatura_num,
            'data_emissao': instance.emissao.isoformat() if instance.emissao else None,
            'estipulante': {
                'name': instance.estipulante_nome,
                'nome': instance.estipulante_nome,
                'cnpj': instance.estipulante_cnpj,
            },
            'uploaderName': instance.uploader_name,
            'uploader_name': instance.uploader_name,
            'usuario_nome': instance.uploader_name,
            'responsavel_nome': instance.uploader_name,
            'created_by_name': instance.uploader_name,
            'uploaderId': user.id if user else None,
            'uploader_id': user.id if user else None,
            'usuario_id': user.id if user else None,
            'responsavel_id': user.id if user else None,
            'manualStatus': instance.manual_status,
            'manual_status': instance.manual_status,
            'status_manual': instance.manual_status,
            'totalCents': instance.total_cents,
            'total_cents': instance.total_cents,
            'valor_total_cents': instance.total_cents,
            'valor_total': instance.total_cents,
            'createdAt': instance.created_at.isoformat() if instance.created_at else None,
            'created_at': instance.created_at.isoformat() if instance.created_at else None,
            'data_criacao': instance.created_at.isoformat() if instance.created_at else None,
            'coEstipulantes': data.get('co_estipulantes', []),
        })
        return data


class FaturaUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    dataCreditoList = serializers.JSONField(required=False, default=None)


class FaturaMoveSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Fatura.STATUS_CHOICES)


class FaturaEnviaCPSerializer(serializers.Serializer):
    formaPagemento = serializers.ChoiceField(choices=[('Boleto', 'Boleto'), ('PIX', 'PIX')])


class BoletoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Boleto
        fields = [
            'id', 'name', 'file_name', 'due_date', 'value_cents',
            'paid_at', 'uploader_name', 'uploader', 'arquivo', 'created_at',
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update({
            'uploaderName': instance.uploader_name,
            'uploader_name': instance.uploader_name,
        })
        return data


class FaturaCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FaturaComment
        fields = ['id', 'text', 'image_data', 'author_name', 'created_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update({
            'authorName': instance.author_name,
            'author_name': instance.author_name,
            'createdAt': instance.created_at.isoformat() if instance.created_at else None,
            'created_at': instance.created_at.isoformat() if instance.created_at else None,
        })
        return data
