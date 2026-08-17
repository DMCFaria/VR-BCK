"""
Suporte à geração do schema OpenAPI 3 (drf-spectacular).

Boa parte da API é escrita com `APIView` pura (sem `serializer_class`), o que
impede o drf-spectacular de inferir corpo de requisição e resposta. Em vez de
deixar esses endpoints fora da documentação, o `VRAutoSchema` abaixo:

- aplica um corpo/resposta genérico (objeto JSON livre) como fallback;
- agrupa as operações em tags de negócio a partir do prefixo da URL.

Endpoints que precisem de contrato detalhado devem ser anotados com
`@extend_schema` na própria view — a anotação sempre tem prioridade sobre o
fallback definido aqui.
"""

from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import OpenApiTypes


# Prefixo da URL (logo após /api/) -> tag exibida no Swagger.
TAGS_POR_PREFIXO = {
    'auth': 'Autenticação',
    'users': 'Usuários',
    'entidades': 'Entidades',
    'beneficios': 'Benefícios',
    'upload': 'Upload',
    'consultas': 'Consultas',
}


class VRAutoSchema(AutoSchema):
    def get_tags(self):
        # Tags explícitas na view (@extend_schema(tags=[...])) têm prioridade.
        tags = super().get_tags()

        partes = [p for p in self.path.split('/') if p]
        if partes and partes[0] == 'api' and len(partes) > 1:
            tag = TAGS_POR_PREFIXO.get(partes[1])
            if tag:
                return [tag]
        return tags

    def _view_tem_serializer(self):
        view = self.view
        return bool(
            getattr(view, 'serializer_class', None)
            or hasattr(view, 'get_serializer')
            or hasattr(view, 'get_serializer_class')
        )

    def get_request_serializer(self):
        if self._view_tem_serializer():
            return super().get_request_serializer()
        # APIView pura: documenta como objeto JSON livre.
        return OpenApiTypes.OBJECT

    def get_response_serializers(self):
        if self._view_tem_serializer():
            return super().get_response_serializers()
        return OpenApiTypes.OBJECT
