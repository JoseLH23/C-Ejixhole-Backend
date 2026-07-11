"""
Arreglo puntual: si ya corriste seed_catalogo_publico.py ANTES de este
cambio, tu servicio "Camping" quedó con categoria="hospedaje" en vez
de "camping". Este script solo corrige esa fila si hace falta —
seguro correrlo aunque ya esté bien (no hace nada en ese caso).

Uso:
    python -m scripts.fix_categoria_camping
"""
from app.database import SessionLocal
from app.models.servicio import Servicio


def main():
    db = SessionLocal()
    try:
        camping = db.query(Servicio).filter(Servicio.nombre == "Camping").first()
        if not camping:
            print("No existe un servicio 'Camping' — nada que corregir (¿corriste el seed?).")
            return
        if camping.categoria == "camping":
            print("Ya está correcto (categoria='camping'). Nada que hacer.")
            return
        anterior = camping.categoria
        camping.categoria = "camping"
        db.commit()
        print(f"Corregido: 'Camping' tenía categoria={anterior!r}, ahora es 'camping'.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
