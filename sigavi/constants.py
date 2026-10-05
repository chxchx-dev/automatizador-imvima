from __future__ import annotations

APP_NAME = "SIGAVI"
APP_VERSION = "1.0.0"
INVIMA_URL = "https://app.invima.gov.co/alertas/alertas-sanitarias-general"
INVIMA_HOST = "https://app.invima.gov.co"
DEFAULT_START_DATE = "2026-08-20"
SHEET_NAME = "Matriz de Alertas 2025"

MATRIX_HEADERS = (
    "FECHA DE REVISION",
    "FECHA DE ALERTA",
    "CÓDIGO DE ALERTA",
    "FUENTE DE LA ALERTA",
    "LINK",
    "TIPO DE ALERTA",
    "TIPO DE PRODUCTO",
    "NOMBRE DEL PRODUCTO",
    "REGISTRO SANITARIO",
    "TITULAR DEL REGISTRO",
    "FABRICANTE / IMPORTADOR",
    "REFERENCIA / CÓDIGO",
    "LOTE/ SERIAL",
    "DESCRIPCIÓN",
    "INDICACIÓN Y USO",
    "SERVICIO QUE UTILIZA",
    "RESULTADO Y SEGUIMIENTO",
    "RESPONSABLE DE LA CONSULTA",
)

PRODUCT_TYPES = (
    "Alimentos y bebidas",
    "Cosmético",
    "Dispositivos médicos sobre medida bucales - Tipología dispositivos sobre medida.",
    "Dispositivos médicos sobre medida de salud visual y ocular - Tipología dispositivos sobre medida.",
    "Dispositivos médicos sobre medida de tecnología ortopédica - Tipología dispositivos sobre medida.",
    "Fitoterapéutico",
    "Homeopático",
    "Medicamento",
    "Subtipología Consumibles o Insumos - Tipología Consumible",
    "Subtipología Implantable - Tipología Consumible",
    "Subtipología Reactivo In vitro y de diagnostico In vitro - Tipología Consumible",
    "Subtipología reutilizables - Tipología Consumible",
    "Suplemento Dietario",
    "Tipología borderline",
    "Tipología DM como Software",
    "Tipología Equipo Biomédico",
)

SURVEILLANCE_TYPES = (
    "Farmacovigilancia",
    "Tecnovigilancia",
    "Reactivovigilancia",
    "Cosmetovigilancia",
    "Alimentovigilancia",
)

SPANISH_MONTHS = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)

SECTION_HEADINGS = (
    "Descripción del caso",
    "Indicaciones y uso establecido",
    "Antecedentes",
    "Medidas para la comunidad en general",
    "Medidas para la comunidad",
    "Medidas para la comunidad médica",
    "Medidas para profesionales de salud",
    "Medidas para profesionales de la salud",
    "Medidas para pacientes y cuidadores",
    "Medidas para usuarios",
    "Medidas para instituciones prestadoras de servicios de salud",
    "Medidas para IPS",
    "Medidas sanitarias",
    "Recomendaciones",
    "Recomendaciones para profesionales de la salud",
    "Acciones a seguir",
    "Acciones para la comunidad en general",
    "Acciones para los profesionales de la salud",
    "Información para profesionales de la salud",
    "Información para pacientes",
    "Información para IPS",
    "Referencias",
    "Bibliografía",
)
