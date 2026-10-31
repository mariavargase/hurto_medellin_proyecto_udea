"""Analisis de hurto por barrio en Medellin.

Pregunta: que barrios concentran el hurto y que politica le corresponde a cada uno.

Decisiones de metodo, todas discutibles y explicadas en el notebook:
  - Ventana 2018-2022. Los datos llegan hasta noviembre de 2023, asi que 2023
    no es un anio comparable.
  - Tasa por 100.000 habitantes y por anio, no conteos. Un barrio con mas gente
    tiene mas hurtos por aritmetica, no por inseguridad.
  - Se descartan los barrios con menos de 2.000 habitantes. El Poblado tiene 408
    residentes registrados pero es el corazon comercial de la ciudad: su tasa
    por residente es un artefacto del denominador, no una medida de peligro.
  - Se separa el hurto a persona (ocurre casi todo en via publica, lo sufre
    quien transita) del hurto a residencia (lo sufre quien vive ahi).
"""
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from libpysal.weights import Queen
from esda.moran import Moran, Moran_Local

sys.path.insert(0, str(Path(__file__).resolve().parent))
import project_notebook.rampa as R  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "datalake" / "data" / "raw" / "medellin"
SEGURIDAD = DATOS / "seguridad"

ANIO_INI, ANIO_FIN = 2018, 2022
ANIOS = ANIO_FIN - ANIO_INI + 1
POBLACION_MINIMA = 2_000       # piso del denominador
ESCALA = 100_000               # tasa por 100.000 habitantes

TIPOS = {
    "hurto_persona.csv": "persona",
    "hurto_residencia.csv": "residencia",
    "hurto_moto.csv": "moto",
    "hurto_carro.csv": "carro",
    "hurto_pirateria_terrestre.csv": "pirateria",
    "hurto_entidad_financiera.csv": "entidad_financiera",
}
# El hurto a persona en via publica es el que define "que tan peligroso es
# caminar este barrio"; el resto tiene otro patron.
DELITO_CALLE = "persona"

ETIQUETAS = {
    "persona": "Hurto a persona",
    "residencia": "Hurto a residencia",
    "moto": "Hurto de moto",
    "carro": "Hurto de carro",
    "pirateria": "Pirateria terrestre",
    "entidad_financiera": "Entidad financiera",
}

# Cortes de la escala. La distribucion tiene asimetria 12: unos pocos barrios
# concentran casi todo. Cortes redondos en la cola y finos al principio, para
# que la escala no gaste clases enteras en barrios que nadie va a mirar.
CORTES = [0, 500, 1_500, 3_000, 8_000, float("inf")]
ETIQUETAS_CLASE = ["< 500", "500 - 1.500", "1.500 - 3.000", "3.000 - 8.000", "> 8.000"]


def cargar_hurtos() -> pd.DataFrame:
    """Una fila por barrio y tipo de hurto, en la ventana de analisis."""
    partes = []
    for archivo, nombre in TIPOS.items():
        ruta = SEGURIDAD / archivo
        if not ruta.exists():
            continue
        df = pd.read_csv(ruta, dtype=str, low_memory=False,
                         usecols=["fecha_hecho", "codigo_barrio", "cantidad"])
        df["anio"] = pd.to_datetime(df["fecha_hecho"], errors="coerce").dt.year
        df = df[df["anio"].between(ANIO_INI, ANIO_FIN)]
        # El codigo viene con '#' adelante: '#1103' -> '1103'
        df["codigo"] = df["codigo_barrio"].str.lstrip("#").str.strip()
        df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(1)
        partes.append(df.groupby("codigo")["cantidad"].sum().rename(nombre))
    return pd.concat(partes, axis=1).fillna(0)


def tasa(conteo: pd.Series, poblacion: pd.Series) -> pd.Series:
    """Hurtos por 100.000 habitantes y por anio."""
    return ESCALA * conteo / poblacion / ANIOS


def construir() -> gpd.GeoDataFrame:
    barrios = gpd.read_file(DATOS / "barrios.geojson")
    barrios = barrios[(barrios["subtipo_barriovereda"] == 1)
                      & ~barrios["codigo"].str.startswith("Inst_")]

    bateria = pd.read_csv(DATOS / "bateria_barrios.csv", dtype=str)
    bateria = bateria[(bateria["Desag"] == "Barrio") & (bateria["Anio"] == "2021")]
    bateria["Valor"] = pd.to_numeric(bateria["Valor"].str.replace(",", "."),
                                     errors="coerce")
    indicadores = bateria.pivot_table(index="Cod_Barrio", columns="Nom_Ind",
                                      values="Valor")
    comunas = bateria.groupby("Cod_Com")["Nom_Com"].first()

    hurtos = cargar_hurtos()
    barrios = barrios.set_index("codigo").join(hurtos, how="inner")
    barrios[list(TIPOS.values())] = barrios[list(TIPOS.values())].fillna(0)
    barrios["poblacion"] = indicadores["Población total"]
    # Barrios de 21 habitantes (Tenche, zona industrial) distorsionan la tasa
    barrios = barrios[barrios["poblacion"] >= POBLACION_MINIMA]
    barrios["comuna"] = barrios["limitecomunacorregimientoid"].map(comunas)
    barrios["estrato_1_2"] = (indicadores["Población estrato 1"]
                              + indicadores["Población estrato 2"])
    barrios["pct_estrato_1_2"] = 100 * barrios["estrato_1_2"] / barrios["poblacion"]

    barrios["total"] = barrios[list(TIPOS.values())].sum(axis=1)
    barrios["tasa"] = tasa(barrios["total"], barrios["poblacion"])
    barrios["tasa_calle"] = tasa(barrios[DELITO_CALLE], barrios["poblacion"])
    barrios["tasa_residencia"] = tasa(barrios["residencia"], barrios["poblacion"])
    return barrios


def clase_de(valor: float) -> str:
    """Etiqueta de la clase a la que cae una tasa."""
    for i in range(len(CORTES) - 1):
        if CORTES[i] <= valor < CORTES[i + 1]:
            return ETIQUETAS_CLASE[i]
    return ETIQUETAS_CLASE[-1]


def color_de(clase: str) -> str:
    """Color de relleno del mapa: rojo mas intenso = mas peligroso."""
    if clase in ETIQUETAS_CLASE:
        return R.ROJA[ETIQUETAS_CLASE.index(clase)]
    return R.SIN_DATOS


def main() -> None:
    barrios = construir()

    print(f"Ventana: {ANIO_INI}-{ANIO_FIN} ({ANIOS} anios)")
    print(f"Barrios: {len(barrios)}  ·  Poblacion: {barrios['poblacion'].sum():,.0f}")
    print(f"Hurtos:  {barrios['total'].sum():,.0f}")
    print(f"Tasa de la ciudad: "
          f"{tasa(barrios['total'].sum(), barrios['poblacion'].sum()):,.0f} "
          f"por 100.000 hab/anio")

    print("\n=== Por tipo de hurto ===")
    for col, etiqueta in ETIQUETAS.items():
        print(f"  {etiqueta:<22} {barrios[col].sum():>9,.0f}")

    print("\n=== Los 15 barrios mas peligrosos (tasa total) ===")
    cols = ["nombre", "comuna", "poblacion", "total", "tasa_calle", "tasa_residencia"]
    peores = barrios.nlargest(15, "tasa")[cols]
    print(peores.round(0).to_string())

    print("\n=== Los 10 barrios mas peligrosos para QUIEN VIVE (hurto a residencia) ===")
    cols_r = ["nombre", "comuna", "poblacion", "residencia", "tasa_residencia"]
    print(barrios.nlargest(10, "tasa_residencia")[cols_r].round(1).to_string())

    print("\n=== Distribucion por clase ===")
    barrios["clase"] = barrios["tasa"].map(clase_de)
    resumen = barrios.groupby("clase").agg(
        barrios=("nombre", "count"), poblacion=("poblacion", "sum"),
        hurtos=("total", "sum"))
    resumen = resumen.reindex(ETIQUETAS_CLASE)
    resumen["pct_hurtos"] = 100 * resumen["hurtos"] / resumen["hurtos"].sum()
    print(resumen.to_string())

    print("\n=== Por comuna ===")
    por_comuna = barrios.groupby("comuna").agg(
        barrios=("nombre", "count"), poblacion=("poblacion", "sum"),
        hurtos=("total", "sum"))
    por_comuna["tasa"] = tasa(por_comuna["hurtos"], por_comuna["poblacion"])
    print(por_comuna.sort_values("tasa", ascending=False).round(0).to_string())

    print("\n=== Autocorrelacion espacial (I de Moran sobre la tasa) ===")
    w = Queen.from_dataframe(barrios, use_index=True)
    w.transform = "r"
    for col in ["tasa", "tasa_calle", "tasa_residencia"]:
        m = Moran(barrios[col], w)
        print(f"  {col:<18} I = {m.I:6.3f}   p = {m.p_sim:.3f}")

    local = Moran_Local(barrios["tasa"], w, seed=0)
    barrios["cuadrante"] = pd.Series(local.q, index=barrios.index).map(
        {1: "Alto-Alto", 2: "Bajo-Alto", 3: "Bajo-Bajo", 4: "Alto-Bajo"})
    barrios.loc[local.p_sim >= 0.05, "cuadrante"] = "No significativo"
    print("\n  Cuadrantes del Moran local:")
    print(barrios.groupby("cuadrante").agg(
        barrios=("nombre", "count"), poblacion=("poblacion", "sum"),
        hurtos=("total", "sum")).to_string())

    print("\n=== Tasa vs estrato (Spearman) ===")
    for col in ["tasa", "tasa_calle", "tasa_residencia"]:
        rho = barrios[col].corr(barrios["pct_estrato_1_2"], method="spearman")
        print(f"  {col:<18} vs % estrato 1-2:  rho = {rho:+.2f}")

    print("\n=== Concentracion ===")
    orden = barrios.sort_values("total", ascending=False)
    for k in (10, 20, 30):
        print(f"  {k:>2} barrios ({k / len(barrios) * 100:4.0f}% de los barrios) "
              f"concentran {100 * orden['total'].head(k).sum() / barrios['total'].sum():4.1f}% "
              f"de los hurtos")

    salida = RAIZ / "datalake" / "data" / "processed" / "hurto"
    salida.mkdir(parents=True, exist_ok=True)
    columnas = ["nombre", "comuna", "poblacion", "pct_estrato_1_2", *TIPOS.values(),
                "total", "tasa", "tasa_calle", "tasa_residencia", "clase",
                "cuadrante", "geometry"]
    tabla = barrios[columnas].reset_index().to_crs(4326)
    tabla.to_file(salida / "barrios_hurto.geojson")
    print(f"\nExportado a {salida / 'barrios_hurto.geojson'}")


if __name__ == "__main__":
    main()
