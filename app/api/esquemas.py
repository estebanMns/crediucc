"""DTOs de entrada/salida HTTP: separan el contrato público del modelo de dominio."""
from pydantic import BaseModel, field_validator

from app.aplicacion.identidad import PerfilRegistro, Sesion, Usuario
from app.dominio.modelos import SolicitudCredito

EDAD_REGISTRO = (16, 100)
SEMESTRE = (1, 12)
LARGO_CLAVE = (8, 72)
CARACTERES_NOMBRE = "'-"


class SolicitudEntrada(BaseModel):
    nombre: str
    email: str
    edad: int
    score: int
    ingresos: float
    monto: float
    es_estudiante: bool = False

    def a_dominio(self) -> SolicitudCredito:
        return SolicitudCredito(**self.model_dump())


def _es_palabra_de_nombre(palabra: str) -> bool:
    """Letras (con tildes y ñ), apóstrofo o guion, y al menos una letra: "Ana --" no es un nombre."""
    return any(c.isalpha() for c in palabra) and all(c.isalpha() or c in CARACTERES_NOMBRE for c in palabra)


def validar_email(valor: str) -> str:
    email = valor.strip().lower()
    usuario, arroba, dominio = email.partition("@")
    valido = (arroba and usuario and "." in dominio and not dominio.startswith(".")
              and not dominio.endswith(".") and "@" not in dominio and " " not in email
              and 3 <= len(email) <= 254)
    if not valido:
        raise ValueError("Escribe un correo válido, por ejemplo nombre@correo.com.")
    return email


class IngresoEntrada(BaseModel):
    """Para ingresar solo se exige lo mínimo: Supabase decide si la contraseña es correcta."""

    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, valor: str) -> str:
        return validar_email(valor)

    @field_validator("password")
    @classmethod
    def _password(cls, valor: str) -> str:
        if not valor or len(valor) > LARGO_CLAVE[1]:
            raise ValueError("Escribe tu contraseña.")
        return valor


class RegistroEntrada(IngresoEntrada):
    nombre_completo: str
    edad: int
    semestre: int

    @field_validator("password")
    @classmethod
    def _password(cls, valor: str) -> str:
        minimo, maximo = LARGO_CLAVE
        segura = (minimo <= len(valor) <= maximo and not any(c.isspace() for c in valor)
                  and any(c.isalpha() for c in valor) and any(c.isdigit() for c in valor))
        if not segura:
            raise ValueError(f"La contraseña debe tener entre {minimo} y {maximo} caracteres, "
                             "con letras y números, y sin espacios.")
        return valor

    @field_validator("nombre_completo")
    @classmethod
    def _nombre(cls, valor: str) -> str:
        palabras = valor.split()
        solo_letras = all(_es_palabra_de_nombre(palabra) for palabra in palabras)
        if len(palabras) < 2 or not solo_letras or not 5 <= len(" ".join(palabras)) <= 120:
            raise ValueError("Escribe tu nombre completo (nombre y apellido), solo con letras.")
        return " ".join(palabra[:1].upper() + palabra[1:] for palabra in palabras)

    @field_validator("edad")
    @classmethod
    def _edad(cls, valor: int) -> int:
        minimo, maximo = EDAD_REGISTRO
        if not minimo <= valor <= maximo:
            raise ValueError(f"La edad debe estar entre {minimo} y {maximo} años.")
        return valor

    @field_validator("semestre")
    @classmethod
    def _semestre(cls, valor: int) -> int:
        minimo, maximo = SEMESTRE
        if not minimo <= valor <= maximo:
            raise ValueError(f"El semestre debe estar entre {minimo} y {maximo}.")
        return valor

    def perfil(self) -> PerfilRegistro:
        return PerfilRegistro(self.nombre_completo, self.edad, self.semestre)


def usuario_a_dict(usuario: Usuario) -> dict:
    return {"id": usuario.id, "email": usuario.email, "nombre_completo": usuario.nombre_completo,
            "edad": usuario.edad, "semestre": usuario.semestre}


def sesion_a_dict(sesion: Sesion) -> dict:
    """El JWT no se devuelve en el cuerpo: viaja solo en la cookie HttpOnly."""
    return {"expira_en": sesion.expira_en_s, "usuario": usuario_a_dict(sesion.usuario)}
