from pathlib import Path
import geopandas as gpd
import pandas as pd

# Raíz del proyecto
RAIZ = Path(__file__).resolve().parents[1]
SALIDA_DEFAULT = RAIZ / "datalake" / "data" / "processed" / "hurto"

def guardar_resultados(barrios, tipos, ruta_salida=SALIDA_DEFAULT):
    """Exporta la tabla final de barrios a formatos GeoJSON y CSV."""
    ruta_salida.mkdir(parents=True, exist_ok=True)
    
    cols = [
        "nombre",
        "comuna", 
        "poblacion", 
        "pct_estrato_1_2",
        *tipos, 
        "total",
        "tasa", 
        "tasa_calle",
        "tasa_residencia",
        "cuadrante",
        "geometry", 
    ]

    # 1. Exportación a GeoJSON (proyección geográfica EPSG: 4326)
    tabla = barrios[cols].reset_index().to_crs(4326)
    tabla.to_file(ruta_salida / "barrios_hurto.geojson")

    # 2. Exportación a CSV ordenado descendentemente por tasa
    tabla.drop(columns="geometry").sort_values("tasa", ascending=False).to_csv( 
        ruta_salida / "tabla_hurto_barrio.csv", index=False, encoding="utf-8" 
    )
    print(f"✅ Exportados {len(tabla)} barrios a {ruta_salida}")