"""Pasada exploratoria: agrega hurtos por barrio y mira la forma de la distribucion."""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
SEG = RAIZ / "datalake" / "data" / "raw" / "medellin" / "seguridad"
RAW = RAIZ / "datalake" / "data" / "raw" / "medellin"

ANIOS = (2018, 2022)  # 2023 llega solo hasta noviembre: no es un anio comparable

TIPOS = {
    "hurto_persona.csv": "persona",
    "hurto_moto.csv": "moto",
    "hurto_residencia.csv": "residencia",
    "hurto_carro.csv": "carro",
    "hurto_pirateria_terrestre.csv": "pirateria",
    "hurto_entidad_financiera.csv": "entidad_financiera",
    "hurto_transporte_publico.csv": "transporte_publico",
}


def cargar() -> pd.DataFrame:
    partes = []
    for archivo, nombre in TIPOS.items():
        ruta = SEG / archivo
        if not ruta.exists():
            print(f"  (falta {archivo})")
            continue
        df = pd.read_csv(ruta, dtype=str, low_memory=False,
                         usecols=["fecha_hecho", "codigo_barrio", "nombre_barrio", "cantidad"])
        df["fecha"] = pd.to_datetime(df["fecha_hecho"], errors="coerce")
        df["anio"] = df["fecha"].dt.year
        df = df[df["anio"].between(*ANIOS)]
        df["tipo"] = nombre
        df["codigo"] = df["codigo_barrio"].str.lstrip("#").str.strip()
        partes.append(df[["codigo", "tipo", "anio", "cantidad"]])
    todo = pd.concat(partes, ignore_index=True)
    todo["cantidad"] = pd.to_numeric(todo["cantidad"], errors="coerce").fillna(1)
    return todo


def poblacion() -> pd.Series:
    b = pd.read_csv(RAW / "bateria_barrios.csv", dtype=str)
    b = b[(b["Desag"] == "Barrio") & (b["Anio"] == "2021")]
    b["Valor"] = pd.to_numeric(b["Valor"].str.replace(",", "."), errors="coerce")
    ind = b.pivot_table(index="Cod_Barrio", columns="Nom_Ind", values="Valor")
    return ind["Población total"]


def main() -> None:
    todo = cargar()
    print(f"\nhurtos en {ANIOS[0]}-{ANIOS[1]}: {len(todo):,}")
    print("\npor tipo:")
    print(todo["tipo"].value_counts().to_string())

    pob = poblacion()
    conteo = todo.pivot_table(index="codigo", columns="tipo", values="cantidad",
                              aggfunc="sum").fillna(0)
    conteo["total"] = conteo.sum(axis=1)
    conteo = conteo.join(pob.rename("poblacion"), how="inner")
    conteo = conteo[conteo["poblacion"] >= 100]

    anios = ANIOS[1] - ANIOS[0] + 1
    conteo["tasa"] = 1e5 * conteo["total"] / conteo["poblacion"] / anios
    print(f"\nbarrios con datos: {len(conteo)}")
    print(f"poblacion cubierta: {conteo['poblacion'].sum():,.0f}")
    print("\ntasa de hurto total por 100.000 hab/anio:")
    print(conteo["tasa"].describe().round(1).to_string())
    print(f"\nasimetria (skew): {conteo['tasa'].skew():.2f}")
    print(f"\ntop 12 barrios por tasa:")
    g = gpd.read_file(RAW / "barrios.geojson")[["codigo", "nombre", "limitecomunacorregimientoid"]]
    j = conteo.join(g.set_index("codigo")[["nombre", "limitecomunacorregimientoid"]])
    cols = ["nombre", "limitecomunacorregimientoid", "poblacion", "total", "tasa"]
    print(j.nlargest(12, "tasa")[cols].round(1).to_string())
    print(f"\nbottom 8:")
    print(j.nsmallest(8, "tasa")[cols].round(1).to_string())
    print(f"\ncorrelacion tasa vs poblacion (spearman): "
          f"{conteo['tasa'].corr(conteo['poblacion'], method='spearman'):.2f}")


if __name__ == "__main__":
    main()
