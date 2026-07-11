"""
Carga el catálogo real de EjiXhole: las 3 unidades de hospedaje y los
servicios reales del parque.

Uso (con tu venv activado y .env apuntando a tu Postgres real):

    python -m scripts.seed_catalogo_publico

AVISO IMPORTANTE: los precios de las 12 actividades informativas
(marcadas PRECIO_PENDIENTE abajo) NO son datos reales — no me los
diste y no los voy a inventar. Se cargan en $0.00 con una nota clara
en la descripción para que no se publiquen por accidente con un precio
falso. Antes de lanzar el catálogo público, edítalos con los precios
reales desde el módulo Servicios que ya existe (no hace falta volver
a correr este script).
"""
from app.database import SessionLocal
from app.models.servicio import Servicio
from app.models.unidad_hospedaje import UnidadHospedaje

PRECIO_PENDIENTE = 0.00
NOTA_PRECIO_PENDIENTE = "PRECIO PENDIENTE — actualizar antes de publicar en el portal."

UNIDADES_HOSPEDAJE = [
    {"nombre": "Habitación 1", "capacidad_maxima": 4, "precio_por_noche": 800.00},
    {"nombre": "Habitación 2", "capacidad_maxima": 4, "precio_por_noche": 800.00},
    {"nombre": "Cabaña 1", "capacidad_maxima": 4, "precio_por_noche": 800.00},
]

# Los 4 servicios reservables/cobrables desde el portal. "Acceso al
# parque" es la entrada base ($50/persona/día); "Camping" es
# $100/persona/noche (además de la entrada); "Cabañas"/"Habitaciones"
# son la categoría a la que pertenece cada UnidadHospedaje (el precio
# real de $800/noche vive en UnidadHospedaje, no aquí — este precio es
# solo referencial para Reportes).
SERVICIOS_RESERVABLES = [
    {"nombre": "Acceso al parque", "precio": 50.00, "categoria": "entrada", "reservable": True},
    {"nombre": "Camping", "precio": 100.00, "categoria": "camping", "reservable": True},
    {"nombre": "Cabañas", "precio": 800.00, "categoria": "hospedaje", "reservable": True},
    {"nombre": "Habitaciones", "precio": 800.00, "categoria": "hospedaje", "reservable": True},
]

# Las 12 actividades informativas: se contratan ya estando en el
# parque, sujeto a disponibilidad — el portal solo las muestra, nunca
# las reserva ni las cobra en línea.
SERVICIOS_INFORMATIVOS = [
    "Paseo en lancha",
    "Paseo a caballo",
    "Senderismo",
    "Renta de chalecos salvavidas",
    "Renta de lancha inflable",
    "Renta de kayaks",
    "Tubing (bajar cascadas en llantas inflables)",
    "Saltos de cascadas",
    "Pesca deportiva",
    "Guías turísticos",
    "Eventos privados",
    "Snorkel",
]


def main():
    db = SessionLocal()
    try:
        for datos in UNIDADES_HOSPEDAJE:
            existente = db.query(UnidadHospedaje).filter(UnidadHospedaje.nombre == datos["nombre"]).first()
            if not existente:
                db.add(UnidadHospedaje(**datos, activa=True))

        for datos in SERVICIOS_RESERVABLES:
            existente = db.query(Servicio).filter(Servicio.nombre == datos["nombre"]).first()
            if not existente:
                db.add(Servicio(**datos, activo=True))

        for nombre in SERVICIOS_INFORMATIVOS:
            existente = db.query(Servicio).filter(Servicio.nombre == nombre).first()
            if not existente:
                db.add(
                    Servicio(
                        nombre=nombre,
                        precio=PRECIO_PENDIENTE,
                        descripcion=NOTA_PRECIO_PENDIENTE,
                        categoria="informativo",
                        reservable=False,
                        activo=True,
                    )
                )

        db.commit()
        print("Catálogo cargado: 3 unidades de hospedaje + 4 servicios reservables + 12 informativos.")
        print("RECORDATORIO: edita los 12 servicios informativos con sus precios reales antes de publicar.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
