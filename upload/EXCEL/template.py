import os
from django.http import HttpResponse
from rest_framework.decorators import api_view


@api_view(['GET'])
def baixar_template_excel(request):
    file_path = os.path.join(os.path.dirname(__file__), 'Template_VR.xlsx')

    with open(file_path, 'rb') as f:
        content = f.read()

    response = HttpResponse(
        content,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="modelo_importacao_vr_completo.xlsx"'

    return response
