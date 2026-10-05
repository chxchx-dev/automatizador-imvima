from __future__ import annotations

import re

from .constants import PRODUCT_TYPES
from .duplicates import normalize_text


def classify_alert(source_category: str, product_name: str, document_text: str = "") -> tuple[str, str, str]:
    """Return an institutional product type only when the available evidence supports it."""
    category = normalize_text(source_category)
    name = normalize_text(product_name)
    text = normalize_text(document_text[:12000])
    product_type = ""
    confidence = "pending"

    if "alimento" in category or "bebida" in category:
        product_type, confidence = PRODUCT_TYPES[0], "high"
    else:
        # INVIMA groups cosmetics, household cleaning products and pesticides together.
        # A pesticide cannot be forced into the institution's current product list.
        pesticide_terms = (
            "plaguicida", "insecticida", "rodenticida", "contra cucarachas",
            "control de plagas", "cebo en gel", "veneno para roedores",
        )
        if any(term in name for term in pesticide_terms):
            return "", "", "pending"

        if "suplemento dietario" in name or (
            "suplemento dietario" in text and re.search(r"se promociona como\s+(?:un\s+)?suplemento dietario", text)
        ):
            product_type, confidence = PRODUCT_TYPES[12], "medium"
        elif any(term in name for term in ("homeopatico", "homeopatia")):
            product_type, confidence = PRODUCT_TYPES[6], "medium"
        elif any(term in name for term in ("fitoterapeutico", "fitoterapia")):
            product_type, confidence = PRODUCT_TYPES[5], "medium"
        else:
            cosmetic_name_terms = (
                "mascarilla", "shampoo", "champu", "acondicionador", "crema capilar",
                "tratamiento capilar", "maquillaje", "labial", "bloqueador solar", "perfume",
            )
            explicit_cosmetic = "cosmetico" in name or "productos cosmeticos sin notificacion" in text
            if "cosm" in category and (explicit_cosmetic or any(term in name for term in cosmetic_name_terms)):
                product_type, confidence = PRODUCT_TYPES[1], "medium"

        if not product_type:
            custom_map = (
                (("salud visual", "ocular", "lente de contacto", "lentes de contacto", "optica"), PRODUCT_TYPES[3]),
                (("bucal", "odontolog", "dental", "protesis dental"), PRODUCT_TYPES[2]),
                (("ortopedic", "ortoped", "protesis externa"), PRODUCT_TYPES[4]),
            )
            if "sobre medida" in name:
                for terms, mapped in custom_map:
                    if any(term in name for term in terms):
                        product_type, confidence = mapped, "medium"
                        break

        if not product_type and any(term in name for term in ("tipologia borderline", "producto borderline", "borderline", "producto frontera", "producto fronterizo")):
            product_type, confidence = PRODUCT_TYPES[13], "medium"
        if not product_type and any(term in name for term in ("software como dispositivo medico", "software as a medical device", "software medico", "sa-md")):
            product_type, confidence = PRODUCT_TYPES[14], "medium"
        if not product_type and any(term in name for term in ("reactivo", "in vitro", "diagnostico in vitro", "prueba diagnostica", "ensayo diagnostico")):
            product_type, confidence = PRODUCT_TYPES[10], "medium"
        if not product_type and any(term in name for term in ("implantable", "implante", "marcapasos", "neuroestimulador", "protesis implantable", "stent")):
            product_type, confidence = PRODUCT_TYPES[9], "medium"
        if not product_type and any(term in name for term in ("equipo biomedico", "monitor de paciente", "analizador", "gastroscopio", "bomba de infusion", "resonancia magnetica", "ventilador mecanico")):
            product_type, confidence = PRODUCT_TYPES[15], "medium"
        if not product_type and any(term in name for term in ("reutilizable", "reutilizables", "reusable", "reusables")):
            product_type, confidence = PRODUCT_TYPES[11], "medium"
        if not product_type and any(term in name for term in ("dispositivo medico", "dispositivos medicos", "insumo medico", "cateter", "jeringa", "sonda", "tubo endotraqueal", "consumible", "instrumental quirurgico")):
            product_type, confidence = PRODUCT_TYPES[8], "medium"
        if not product_type and "medicamento" in category:
            product_type, confidence = PRODUCT_TYPES[7], "medium"

    if not product_type:
        return "", "", "pending"

    if product_type == PRODUCT_TYPES[0]:
        surveillance = "Alimentovigilancia"
    elif product_type == PRODUCT_TYPES[1]:
        surveillance = "Cosmetovigilancia"
    elif product_type == PRODUCT_TYPES[10]:
        surveillance = "Reactivovigilancia"
    elif product_type == PRODUCT_TYPES[13]:
        surveillance = ""
        confidence = "pending"
    elif product_type in PRODUCT_TYPES[2:5] or product_type in PRODUCT_TYPES[8:12] or product_type in (PRODUCT_TYPES[14], PRODUCT_TYPES[15]):
        surveillance = "Tecnovigilancia"
    else:
        surveillance = "Farmacovigilancia"
    return product_type, surveillance, confidence
