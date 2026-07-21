import logging
from datetime import datetime

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, views, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Fatura, CoEstipulante, Boleto, FaturaComment
from .serializers import (
    FaturaSerializer,
    FaturaUploadSerializer,
    FaturaMoveSerializer,
    FaturaEnviaCPSerializer,
    CoEstipulanteSerializer,
    BoletoSerializer,
    FaturaCommentSerializer,
)

logger = logging.getLogger(__name__)


class FaturaViewSet(viewsets.ModelViewSet):
    queryset = Fatura.objects.prefetch_related('co_estipulantes').all()
    serializer_class = FaturaSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        return Fatura.objects.prefetch_related('co_estipulantes').order_by('-created_at')

    def destroy(self, request, *args, **kwargs):
        fatura = self.get_object()
        fatura.delete()
        return Response({'success': True}, status=status.HTTP_200_OK)


class FaturaParseView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'Nenhum arquivo enviado.'}, status=400)

        try:
            import pdfplumber
            import re

            with pdfplumber.open(file) as pdf:
                full_text = ''
                for page in pdf.pages:
                    full_text += page.extract_text() or ''

            fatura_num = ''
            emissao = ''
            estipulante_nome = ''
            estipulante_cnpj = ''
            co_estipulantes = []

            lines = full_text.split('\n')

            for line in lines:
                if 'fatura' in line.lower() or 'nº' in line.lower() or 'numero' in line.lower():
                    nums = re.findall(r'\d[\d.\-/]+', line)
                    if nums and not fatura_num:
                        fatura_num = nums[0]

                if 'emiss' in line.lower():
                    dates = re.findall(r'\d{2}/\d{2}/\d{4}', line)
                    if dates and not emissao:
                        emissao = dates[0]

                if 'estipulante' in line.lower() or 'contratante' in line.lower():
                    parts = line.split(':')
                    if len(parts) > 1:
                        estipulante_nome = parts[1].strip()
                    cnpjs = re.findall(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', line)
                    if cnpjs:
                        estipulante_cnpj = cnpjs[0]

            return Response({
                'faturaNum': fatura_num,
                'emissao': emissao,
                'estipulante': {
                    'name': estipulante_nome,
                    'cnpj': estipulante_cnpj,
                },
                'coEstipulantes': co_estipulantes,
            })

        except Exception as e:
            logger.error(f"Erro ao parsear PDF: {str(e)}")
            return Response({'detail': f'Erro ao processar PDF: {str(e)}'}, status=400)


class FaturaParseBoletoView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'Nenhum arquivo enviado.'}, status=400)

        try:
            return Response({
                'beneficiario': '',
                'cpfCnpj': '',
                'pagador': '',
                'cnpjPagador': '',
                'valorCents': 0,
                'dataVencimento': '',
                'banco': '',
                'agencia': '',
                'conta': '',
                'linhaDigitavel': '',
            })
        except Exception as e:
            return Response({'detail': str(e)}, status=400)


class FaturaUploadView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'Nenhum arquivo enviado.'}, status=400)

        data_credito_list_raw = request.data.get('dataCreditoList')
        data_credito_list = None
        if data_credito_list_raw:
            import json
            try:
                data_credito_list = json.loads(data_credito_list_raw)
            except Exception:
                pass

        try:
            fatura = Fatura.objects.create(
                fatura_num=file.name.split('.')[0] if file.name else 'Sem número',
                estipulante_nome='',
                uploader_name=request.user.email if request.user else '',
                uploader=request.user,
                arquivo_pdf=file,
            )

            return Response(FaturaSerializer(fatura).data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Erro ao salvar fatura: {str(e)}")
            return Response({'detail': str(e)}, status=400)


class FaturaPagoTodosView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, pk):
        try:
            fatura = Fatura.objects.get(id=pk)
        except Fatura.DoesNotExist:
            return Response({'detail': 'Fatura não encontrada.'}, status=404)

        now = timezone.now()
        fatura.co_estipulantes.update(paid_at=now)
        fatura.manual_status = 'pago'
        fatura.save(update_fields=['manual_status'])

        return Response({'success': True})


class FaturaMoveView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def patch(self, request, pk):
        try:
            fatura = Fatura.objects.get(id=pk)
        except Fatura.DoesNotExist:
            return Response({'detail': 'Fatura não encontrada.'}, status=404)

        new_status = request.data.get('status')
        valid_statuses = [choice[0] for choice in Fatura.STATUS_CHOICES]

        if new_status not in valid_statuses:
            return Response({'detail': f'Status inválido: {new_status}'}, status=400)

        fatura.manual_status = new_status
        fatura.save(update_fields=['manual_status'])

        return Response({'success': True})


class FaturaEnviaCPView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, pk):
        try:
            fatura = Fatura.objects.get(id=pk)
        except Fatura.DoesNotExist:
            return Response({'detail': 'Fatura não encontrada.'}, status=404)

        forma_pagamento = request.data.get('formaPagemento', 'Boleto')

        fatura.co_estipulantes.update(sent_to_cp=True)

        for co in fatura.co_estipulantes.all():
            co.forma_pagamento = forma_pagamento
            co.save(update_fields=['forma_pagamento'])

        return Response({
            'sent': fatura.co_estipulantes.count(),
            'ok': True,
            'errors': [],
            'erros': [],
            'enviados': fatura.co_estipulantes.count(),
            'total_enviados': fatura.co_estipulantes.count(),
        })


class FaturaGerarBoletoVRView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, pk):
        try:
            fatura = Fatura.objects.get(id=pk)
        except Fatura.DoesNotExist:
            return Response({'detail': 'Fatura não encontrada.'}, status=404)

        return Response({'success': True})


class FaturaUploadBoletoVRView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, pk):
        try:
            fatura = Fatura.objects.get(id=pk)
        except Fatura.DoesNotExist:
            return Response({'detail': 'Fatura não encontrada.'}, status=404)

        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'Nenhum arquivo enviado.'}, status=400)

        return Response({
            'success': True,
            'fileName': file.name,
        })


class CoEstipulantePagoView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, pk, idx):
        try:
            fatura = Fatura.objects.get(id=pk)
        except Fatura.DoesNotExist:
            return Response({'detail': 'Fatura não encontrada.'}, status=404)

        try:
            co = fatura.co_estipulantes.get(id=idx)
        except CoEstipulante.DoesNotExist:
            return Response({'detail': 'Co-estipulante não encontrado.'}, status=404)

        if co.paid_at:
            co.paid_at = None
        else:
            co.paid_at = timezone.now()

        co.save(update_fields=['paid_at'])

        return Response({'success': True, 'paid': bool(co.paid_at)})


class FaturaCommentsView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, pk):
        try:
            fatura = Fatura.objects.get(id=pk)
        except Fatura.DoesNotExist:
            return Response({'detail': 'Fatura não encontrada.'}, status=404)

        comments = fatura.comments.all()
        serializer = FaturaCommentSerializer(comments, many=True)
        return Response(serializer.data)

    def post(self, request, pk):
        try:
            fatura = Fatura.objects.get(id=pk)
        except Fatura.DoesNotExist:
            return Response({'detail': 'Fatura não encontrada.'}, status=404)

        text = request.data.get('text', '')
        image_data = request.data.get('imageData')

        comment = FaturaComment.objects.create(
            fatura=fatura,
            text=text,
            image_data=image_data,
            author_name=request.user.email if request.user else '',
        )

        return Response(FaturaCommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class FaturaBoletoVRPdfView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, pk):
        try:
            fatura = Fatura.objects.get(id=pk)
        except Fatura.DoesNotExist:
            return Response({'detail': 'Fatura não encontrada.'}, status=404)

        if fatura.arquivo_pdf:
            response = HttpResponse(fatura.arquivo_pdf.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{fatura.fatura_num}-boleto-vr.pdf"'
            return response

        return Response({'detail': 'PDF não disponível.'}, status=404)


class CoEstipulanteBoletoVRPdfView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, pk, idx):
        try:
            fatura = Fatura.objects.get(id=pk)
        except Fatura.DoesNotExist:
            return Response({'detail': 'Fatura não encontrada.'}, status=404)

        return Response({'detail': 'PDF não disponível.'}, status=404)


class CoEstipulanteBoletoOriginalPdfView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, pk, idx):
        try:
            fatura = Fatura.objects.get(id=pk)
        except Fatura.DoesNotExist:
            return Response({'detail': 'Fatura não encontrada.'}, status=404)

        return Response({'detail': 'PDF não disponível.'}, status=404)


class BoletoViewSet(viewsets.ModelViewSet):
    queryset = Boleto.objects.all()
    serializer_class = BoletoSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def destroy(self, request, *args, **kwargs):
        boleto = self.get_object()
        boleto.delete()
        return Response({'success': True}, status=status.HTTP_200_OK)


class BoletoUploadView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'Nenhum arquivo enviado.'}, status=400)

        boleto = Boleto.objects.create(
            name=file.name.split('.')[0] if file.name else 'Sem nome',
            file_name=file.name or '',
            uploader_name=request.user.email if request.user else '',
            uploader=request.user,
            arquivo=file,
        )

        return Response(BoletoSerializer(boleto).data, status=status.HTTP_201_CREATED)


class BoletoUploadersView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        uploaders = (
            Boleto.objects
            .exclude(uploader_name='')
            .values_list('uploader_name', flat=True)
            .distinct()
        )
        return Response({'data': list(uploaders)})


class BoletoPagoView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, pk):
        try:
            boleto = Boleto.objects.get(id=pk)
        except Boleto.DoesNotExist:
            return Response({'detail': 'Boleto não encontrado.'}, status=404)

        method = request.data.get('method', '')
        boleto.paid_at = timezone.now()
        boleto.save(update_fields=['paid_at'])

        return Response({'success': True})


class BoletoMarkPaidView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, pk):
        try:
            boleto = Boleto.objects.get(id=pk)
        except Boleto.DoesNotExist:
            return Response({'detail': 'Boleto não encontrado.'}, status=404)

        boleto.paid_at = timezone.now()
        boleto.save(update_fields=['paid_at'])

        return Response({'success': True})


class BoletoDownloadView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, pk):
        try:
            boleto = Boleto.objects.get(id=pk)
        except Boleto.DoesNotExist:
            return Response({'detail': 'Boleto não encontrado.'}, status=404)

        if boleto.arquivo:
            response = HttpResponse(boleto.arquivo.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{boleto.file_name or boleto.name}"'
            return response

        return Response({'detail': 'Arquivo não disponível.'}, status=404)


class ReportUploadsPdfView(views.APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        return Response({'detail': 'Relatório não disponível.'}, status=404)
