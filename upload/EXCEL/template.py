import os
from django.http import HttpResponse
from rest_framework.decorators import api_view


@api_view(['GET'])
def baixar_template_VR(request):
    file_path = os.path.join(os.path.dirname(__file__), 'Template_VR.xlsm')

    with open(file_path, 'rb') as f:
        content = f.read()

    response = HttpResponse(
        content,
        content_type='application/vnd.ms-excel.sheet.macroEnabled.12'
    )
    response['Content-Disposition'] = 'attachment; filename="modelo_importacao_vr.xlsm"'

    return response

@api_view(['GET'])
def baixar_template_VT(request):
    file_path = os.path.join(os.path.dirname(__file__), 'Template_VT.xlsx')

    with open(file_path, 'rb') as f:
        content = f.read()

    response = HttpResponse(
        content,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="modelo_importacao_vt.xlsx"'

    return response