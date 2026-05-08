# utils/renderers.py
from rest_framework.renderers import BaseRenderer

class BinaryRenderer(BaseRenderer):
    media_type = '*/*'
    format = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data
