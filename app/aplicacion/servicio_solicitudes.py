"""Caso de uso principal: radicar y consultar solicitudes de microcrédito."""
from app.aplicacion.puertos import CentralRiesgo, PublicadorEventos, RepositorioSolicitudes
from app.dominio.evaluador import EvaluadorCredito
from app.dominio.modelos import SolicitudCredito, SolicitudRegistrada


class SolicitudNoEncontradaError(LookupError):
    def __init__(self, solicitud_id: int) -> None:
        super().__init__(f"Solicitud {solicitud_id} no encontrada")
        self.solicitud_id = solicitud_id


class ServicioSolicitudes:
    """SRP: coordina el flujo; las decisiones de negocio viven en el dominio."""

    def __init__(
        self,
        evaluador: EvaluadorCredito,
        repositorio: RepositorioSolicitudes,
        publicador: PublicadorEventos,
        central_riesgo: CentralRiesgo,
    ) -> None:
        self._evaluador = evaluador
        self._repositorio = repositorio
        self._publicador = publicador
        self._central_riesgo = central_riesgo

    def radicar(self, solicitud: SolicitudCredito, usuario_id: str | None = None) -> SolicitudRegistrada:
        resultado = self._evaluador.evaluar(solicitud)
        self._central_riesgo.consultar(solicitud)
        registro = self._repositorio.agregar(solicitud, resultado, usuario_id)
        if resultado.es_aprobado:
            registro = registro.con_notificacion(self._publicador.publicar_aprobacion(registro))
            self._repositorio.actualizar(registro)
        return registro

    def obtener(self, solicitud_id: int, usuario_id: str | None = None) -> SolicitudRegistrada:
        """Una solicitud de otro usuario se trata como inexistente (no se revela que existe)."""
        registro = self._repositorio.obtener(solicitud_id, usuario_id)
        if registro is None:
            raise SolicitudNoEncontradaError(solicitud_id)
        return registro

    def listar(self, usuario_id: str | None = None) -> list[SolicitudRegistrada]:
        return self._repositorio.listar(usuario_id)
