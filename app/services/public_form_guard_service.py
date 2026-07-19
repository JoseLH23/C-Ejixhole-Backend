from app.services.formulario_publico_service import FormularioPublicoService


class PublicFormGuardService(FormularioPublicoService):
    def validate_and_record(self, request, data):
        return self.validate_and_reserve(request, data)
