"""Construcción del notebook con base en la última sesión de clase 06 y a partir de celdas declaradas aqui.

- Aqui las celdas son tuplas (tipo, texto) y el JSON lo arma json.dump.

- El notebook es AUTOCONTENIDO, como las demas sesiones del curso.

- Las URLs de descarga se sacaron del catalogo MEData
(https://medata.gov.co/data.json, campo distribution[].downloadURL).
"""
import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
KERNEL = {
    "display_name": "python-for-macroeconomic-analysis (3.12.x)",
    "language": "python",
    "name": "python3",
}
LANGINFO = {
    "codemirror_mode": {"name": "ipython", "version": 3},
    "file_extension": ".py",
    "mimetype": "text/x-python",
    "name": "python",
    "nbconvert_exporter": "python",
    "pygments_lexer": "ipython3",
    "version": "3.12.-1",
}

CELDAS = [
("md", """# Sesión 8: ¿Dónde se roba en Medellín?

**Curso:** Python 3 · Modelos Macroeconómicos

**Objetivos de la sesión:**
- Bajar los datos de hurto de MEData y **agregarlos por barrio**
- Convertir conteos en **tasas**: por qué un barrio con más gente no es más peligroso
- Ver el sesgo del **denominador** cuando el barrio es comercial y no residencial
- Mapear con una **escala secuencial de un solo tono**: más rojo, más peligro
- Separar el hurto **en la calle** del hurto **a la casa**: no son el mismo problema
- De ahí a la **política**: qué instrumento le corresponde a cada patrón"""),

("md", """---

# Contexto para el caso presente:

## El caso: el hurto se concentra donde está la plata

En la sesión 6 vimos que el **entorno urbano** malo se concentra en la periferia
pobre: Manrique, Popular, la ladera nororiental. Ese es el mapa de la *carencia*.

El hurto dibuja **el mapa contrario**. Los barrios con más hurtos por habitante de
Medellín son La Candelaria, Laureles y El Poblado — los más ricos y los más
transitados. La correlación entre la tasa de hurto y el porcentaje de población en
estratos 1 y 2 es **−0,86**.

Eso no significa que la pobreza no importe. Significa que **el hurto es un delito
de oportunidad**: ocurre donde hay víctimas con qué robar y flujo de gente. La
carencia y el hurto son dos problemas distintos, con políticas distintas.

### Lectura: medir el delito en cinco ideas

1. **Un conteo no es una tasa.** El barrio más poblado casi siempre tendrá más
   hurtos. Sin dividir por población, el mapa solo dice dónde vive la gente.
2. **El denominador puede mentir.** El Poblado tiene 408 residentes registrados y
   es el corazón comercial de la ciudad. Su tasa por residente es un artefacto.
3. **No todos los hurtos son el mismo delito.** El hurto a persona ocurre en vía
   pública (83.479 de 184.582 casos) y lo sufre quien transita. El hurto a
   residencia lo sufre quien vive ahí. Confundirlos lleva a la política equivocada.
4. **La escala del mapa es una decisión.** Con los mismos datos, cortes distintos
   pintan ciudades distintas.
5. **Un mapa no es una política.** Dice dónde; el *qué* sale de cruzar lugar,
   modalidad y hora.

### Preguntas guía que este notebook responde

1. ¿Qué barrios concentran el hurto? ¿Es la periferia pobre, como el entorno urbano?
2. ¿Cambia el mapa si miramos el hurto a la casa en vez del hurto en la calle?
3. ¿Qué política le corresponde a cada patrón?

### Preguntas de discusión

1. Si el hurto se concentra en los barrios ricos, ¿debería el presupuesto de
   seguridad ir allá y el de vivienda a la periferia? ¿O es la misma plata?
2. El Poblado aparece primero o último según cómo se mida. ¿Qué denominador usarían
   para un barrio que recibe 200.000 visitantes diarios y tiene 408 residentes?
3. La policía se despliega por cuadrante, y los cuadrantes son geográficos. Si el
   delito es de oportunidad y se mueve, ¿tiene sentido un despliegue fijo?"""),

("md", """---

## 1. Los datos

Siete conjuntos de MEData, todos con **código de barrio** y fecha del hecho, de
2003 a noviembre de 2023. Seis entran al análisis; el séptimo se descarta.

| Capa | Qué trae |
|---|---|
| **Hurto a persona** | 326.489 casos; lugar, modalidad, arma, sexo, edad |
| **Hurto a residencia** | 42.673 casos |
| **Hurto de moto / carro** | 86.410 y 39.571 casos |
| **Piratería terrestre, entidad financiera** | 2.202 y 289 casos |
| ~~Hurto a establecimiento comercial~~ | 16.950 casos, **solo hasta 2017** |

**Dos decisiones sobre la ventana temporal:**

- Los datos llegan hasta el **30 de noviembre de 2023**. Incluir 2023 compararía
  once meses contra doce: lo dejamos por fuera y trabajamos **2018–2022**.
- `hurto a establecimiento comercial` se corta en **2017**: no entra.

Las descargas se guardan en `datalake/data/raw/medellin/` y no se vuelven a bajar
si el archivo ya está, igual que en la sesión 6."""),

("code", """from pathlib import Path

import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from esda.moran import Moran, Moran_Local
from libpysal.weights import Queen

RAIZ = Path.cwd().parents[1]
DATOS = RAIZ / "datalake/data/raw/medellin"
SEGURIDAD = DATOS / "seguridad"
SALIDA = RAIZ / "datalake/data/processed/hurto"
DATOS.mkdir(parents=True, exist_ok=True)


def descargar(url, archivo, carpeta=DATOS):
    \"\"\"Baja `url` una vez y reutiliza la copia local.\"\"\"
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / archivo
    if not ruta.exists():
        # Sin User-Agent el servidor de la Alcaldía responde 403
        respuesta = requests.get(url, headers={"User-Agent": "Mozilla/5.0"},
                                 timeout=600)
        respuesta.raise_for_status()
        ruta.write_bytes(respuesta.content)
    return ruta


MEDATA = "https://medata.app.medellin.gov.co/sites/default/files/distribution"
MAPAS = "https://www.medellin.gov.co/servidormapas/rest/services/ServiciosCiudad"

URLS = {
    "persona": f"{MEDATA}/1-027-23-000011/hurto_a_persona.csv",
    "residencia": f"{MEDATA}/1-027-23-000012/hurto_a_residencia.csv",
    "moto": f"{MEDATA}/1-027-23-000014/hurto_de_moto.csv",
    "carro": f"{MEDATA}/1-027-23-000013/hurto_de_carro.csv",
    "pirateria": f"{MEDATA}/1-027-23-000016/hurto_por_pirateria_terrestre.csv",
    "entidad_financiera": f"{MEDATA}/1-027-23-000009/hurto_a_entidad_financiera.csv",
}
URL_BARRIOS = (f"{MAPAS}/MAP6_Indicadores/MapServer/6/query?where=1%3D1"
               "&outFields=codigo,nombre,limitecomunacorregimientoid,"
               "subtipo_barriovereda&outSR=4326&f=geojson")
URL_BATERIA = (f"{MEDATA}/1-002-26-000595/"
               "base_datos_bateria_indicadores_capacidad_soporte_barrio.csv")

ARCHIVOS = {clave: descargar(url, f"hurto_{clave}.csv", SEGURIDAD)
            for clave, url in URLS.items()}
print(f"{len(ARCHIVOS)} conjuntos de hurto en {SEGURIDAD}")"""),

("md", """---

## 2. Agregar por barrio

Cada archivo trae una fila por hecho. Los agrupamos por `codigo_barrio`.

Dos detalles que cuestan horas si no se ven:

- El código viene con un **`#` adelante** (`#1103`). Sin quitarlo, el join contra
  el geojson devuelve cero filas y no dice por qué.
- Hay códigos que no son barrios: `Inst_14`, `AUC2`, `AE1`, `SIN DATO`. Son
  equipamientos, instituciones y áreas de interés, no barrios: se caen solos al
  hacer el join contra el geojson.

La tasa se calcula **por 100.000 habitantes y por año**, para que sea comparable
entre barrios y no dependa de cuántos años se miraron:

$$\\text{tasa}_b = \\frac{\\text{hurtos}_b}{\\text{población}_b} \\times 100.000 \\div \\text{años}$$"""),

("code", """ANIO_INI, ANIO_FIN = 2018, 2022
ANIOS = ANIO_FIN - ANIO_INI + 1
POBLACION_MINIMA = 2_000    # piso del denominador
ESCALA = 100_000            # tasa por 100.000 habitantes


def cargar_hurtos():
    \"\"\"Una columna por tipo de hurto, indexada por código de barrio.\"\"\"
    partes = []
    for clave, ruta in ARCHIVOS.items():
        df = pd.read_csv(ruta, dtype=str, low_memory=False,
                         usecols=["fecha_hecho", "codigo_barrio", "cantidad"])
        df["anio"] = pd.to_datetime(df["fecha_hecho"], errors="coerce").dt.year
        df = df[df["anio"].between(ANIO_INI, ANIO_FIN)]
        # El codigo viene con '#' adelante: '#1103' -> '1103'
        df["codigo"] = df["codigo_barrio"].str.lstrip("#").str.strip()
        df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(1)
        partes.append(df.groupby("codigo")["cantidad"].sum().rename(clave))
    return pd.concat(partes, axis=1).fillna(0)


def tasa(conteo, poblacion):
    \"\"\"Hurtos por 100.000 habitantes y por año.\"\"\"
    return ESCALA * conteo / poblacion / ANIOS


TIPOS = list(URLS)
hurtos = cargar_hurtos()
print(f"Hurtos 2018-2022 en {len(hurtos)} códigos de barrio")
print(hurtos.sum().sort_values(ascending=False).to_string())"""),

("code", """barrios = gpd.read_file(descargar(URL_BARRIOS, "barrios.geojson"))
barrios = barrios[(barrios["subtipo_barriovereda"] == 1)
                  & ~barrios["codigo"].str.startswith("Inst_")]

bateria = pd.read_csv(descargar(URL_BATERIA, "bateria_barrios.csv"), dtype=str)
bateria = bateria[(bateria["Desag"] == "Barrio") & (bateria["Anio"] == "2021")]
bateria["Valor"] = pd.to_numeric(bateria["Valor"].str.replace(",", "."),
                                 errors="coerce")
indicadores = bateria.pivot_table(index="Cod_Barrio", columns="Nom_Ind",
                                  values="Valor")
COMUNAS = bateria.groupby("Cod_Com")["Nom_Com"].first()

barrios = barrios.set_index("codigo").join(hurtos, how="inner")
barrios[TIPOS] = barrios[TIPOS].fillna(0)
barrios["poblacion"] = indicadores["Población total"]
barrios["comuna"] = barrios["limitecomunacorregimientoid"].map(COMUNAS)
barrios["estrato_1_2"] = (indicadores["Población estrato 1"]
                          + indicadores["Población estrato 2"])
barrios["pct_estrato_1_2"] = 100 * barrios["estrato_1_2"] / barrios["poblacion"]

# Barrios de 21 habitantes (Tenche, zona industrial) distorsionan la tasa
barrios = barrios[barrios["poblacion"] >= POBLACION_MINIMA]

barrios["total"] = barrios[TIPOS].sum(axis=1)
barrios["tasa"] = tasa(barrios["total"], barrios["poblacion"])
# El hurto a persona ocurre casi todo en via publica: es el riesgo de transitar.
# El hurto a residencia es el riesgo de quien vive ahi. No son lo mismo.
barrios["tasa_calle"] = tasa(barrios["persona"], barrios["poblacion"])
barrios["tasa_residencia"] = tasa(barrios["residencia"], barrios["poblacion"])

print(f"Ventana: {ANIO_INI}-{ANIO_FIN} ({ANIOS} años)")
print(f"Barrios: {len(barrios)}  ·  Población: {barrios['poblacion'].sum():,.0f}")
print(f"Hurtos: {barrios['total'].sum():,.0f}")
print(f"Tasa de la ciudad: "
      f"{tasa(barrios['total'].sum(), barrios['poblacion'].sum()):,.0f} "
      f"por 100.000 hab/año")"""),

("md", """### El sesgo del denominador

El Poblado tiene **408 residentes registrados** y es el corazón comercial de la
ciudad. Su tasa de 228.382 por 100.000 está entre las más altas de Medellín — y es
falsa: el denominador no son 408 personas, son las decenas de miles que pasan por
ahí. El caso extremo es **Tenche**, con 21 habitantes y 404 hurtos: 384.762 por
100.000. Tenche es una zona industrial y no vive nadie. La tasa de un barrio así
no mide peligro, mide cuánta gente pasa por un lugar donde nadie duerme.

Por eso exigimos **≥ 2.000 habitantes**. Es un parche, no una solución: la solución
es un denominador de **población flotante** (visitantes-día), que la ciudad no
publica por barrio."""),

("code", """cols = ["nombre", "comuna", "poblacion", "pct_estrato_1_2", "total",
        "tasa", "tasa_calle", "tasa_residencia"]
print("=== Los 10 barrios con más hurto por habitante ===")
print(barrios.nlargest(10, "tasa")[cols].round(0).to_string(index=False))"""),

("md", """Los diez primeros son **La Candelaria** (el centro), **Laureles** y **El Poblado**.
Ni uno solo está en la periferia pobre. Compárese con la sesión 6, donde cinco de
los diez peores entornos urbanos estaban en Manrique, en la ladera nororiental.

### El hurto sigue a la plata, no a la carencia

| Grupo de barrios | Barrios | Población | Hurtos | Tasa |
|---|---|---|---|---|
| Ricos (< 20% estrato 1-2) | 119 | 958.000 | 147.355 | **3.076** |
| Medios | 34 | 391.000 | 19.208 | 981 |
| Pobres (> 80% estrato 1-2) | 77 | 872.000 | 18.963 | **435** |

Un barrio rico tiene **siete veces** la tasa de hurto de uno pobre. La correlación
de rangos es **−0,86**."""),

("code", """print("Tasa por grupo socioeconómico")
for etiqueta, sub in [
    ("Ricos  (<20% estrato 1-2)", barrios[barrios["pct_estrato_1_2"] < 20]),
    ("Medios (20-80%)", barrios[(barrios["pct_estrato_1_2"] >= 20)
                                & (barrios["pct_estrato_1_2"] < 80)]),
    ("Pobres (>80% estrato 1-2)", barrios[barrios["pct_estrato_1_2"] >= 80]),
]:
    print(f"  {etiqueta:<26} n={len(sub):>3}  "
          f"población={sub['poblacion'].sum():>9,.0f}  "
          f"hurtos={sub['total'].sum():>7,.0f}  "
          f"tasa={tasa(sub['total'].sum(), sub['poblacion'].sum()):>6,.0f}")

print()
for col in ["tasa", "tasa_calle", "tasa_residencia"]:
    rho = barrios[col].corr(barrios["pct_estrato_1_2"], method="spearman")
    print(f"  {col:<18} vs % estrato 1-2:  rho = {rho:+.2f}")"""),

("md", """---

## 3. El mapa: una escala de un solo tono

Una escala de magnitud usa **un solo tono**, de claro a oscuro. Más oscuro = más.
Un arcoíris haría que el lector compare tonos en vez de magnitudes.

Elegimos **rojo** porque el rojo es calor semántico: en un mapa de delito, rojo ya
significa peligro. Los cortes son fijos y redondos, no cuantiles, para que dos
barrios se puedan comparar sin recalcular.

| Clase | Hurtos por 100.000 hab/año |
|---|---|
| Clase 1 | menos de 500 |
| Clase 2 | 500 – 1.500 |
| Clase 3 | 1.500 – 3.000 |
| Clase 4 | 3.000 – 8.000 |
| Clase 5 | más de 8.000 |

Dos decisiones sobre la escala:

- **El gris no es un valor de la escala.** Está reservado para "sin datos", que es
  un canal distinto. Si el gris fuera la clase más clara, un barrio sin dato y un
  barrio con poco hurto se verían igual.
- **Cada mapa lleva su propia escala.** El hurto en la calle llega a 111.000 y el
  hurto a la casa a 908. Con cortes compartidos, el segundo mapa caería entero en
  la primera clase y no diría nada.

La rampa se construye en **OKLCH**, que es un espacio de color donde la distancia
numérica se parece a lo que el ojo percibe. Un rojo que solo pierde saturación al
oscurecerse termina pardo; por eso aquí la saturación sube y se mantiene, y el tono
se corre un poco hacia el rojo puro en los pasos oscuros."""),

("code", """import math


def _srgb_a_lineal(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _lineal_a_srgb(c):
    v = 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055
    return max(0, min(255, round(255 * v)))


def _lineal_a_oklab(r, g, b):
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (x ** (1 / 3) if x >= 0 else -((-x) ** (1 / 3)) for x in (l, m, s))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def _oklab_a_lineal(L, a, bb):
    l_ = L + 0.3963377774 * a + 0.2158037573 * bb
    m_ = L - 0.1055613458 * a - 0.0638541728 * bb
    s_ = L - 0.0894841775 * a - 1.2914855480 * bb
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (+4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def oklch_a_hex(L, C, H):
    a = C * math.cos(math.radians(H))
    bb = C * math.sin(math.radians(H))
    return "#{:02x}{:02x}{:02x}".format(
        *[_lineal_a_srgb(v) for v in _oklab_a_lineal(L, a, bb)])


def oklch(hex_):
    \"\"\"hex -> (L, C, H). H en grados.\"\"\"
    h = hex_.lstrip("#")
    r, g, b = (_srgb_a_lineal(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    L, a, bb = _lineal_a_oklab(r, g, b)
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def deltaE(a, b):
    \"\"\"Distancia en OKLab x100. Regla práctica: menos de 8 no se distingue.\"\"\"
    h1 = a.lstrip("#")
    h2 = b.lstrip("#")
    La, aa, ba = _lineal_a_oklab(*(_srgb_a_lineal(int(h1[i:i + 2], 16) / 255)
                                   for i in (0, 2, 4)))
    Lb, ab, bb2 = _lineal_a_oklab(*(_srgb_a_lineal(int(h2[i:i + 2], 16) / 255)
                                    for i in (0, 2, 4)))
    return 100 * math.sqrt((La - Lb) ** 2 + (aa - ab) ** 2 + (ba - bb2) ** 2)


HUE_BASE = oklch("#e34948")[2]   # el rojo categórico de la paleta del curso
HUE_PELIGRO = 29.0               # rojo puro al que se corre el extremo oscuro
C_PISO_FRAC = 0.30               # saturación mínima del paso más claro
SIN_DATOS = "#b8b8b8"            # gris neutro, FUERA de la rampa


def rampa(pasos=5, L_ini=0.96, L_fin=0.45, C_pico=0.20, sesgo=0.55):
    \"\"\"Rampa de un tono, claro -> oscuro. Más oscuro = más hurtos.\"\"\"
    salida = []
    for i in range(pasos):
        t = i / (pasos - 1)
        L = L_ini + (L_fin - L_ini) * t
        # Sin el piso de saturación el paso más claro sale gris puro y se
        # confunde con "sin datos", que es otro canal.
        C = C_pico * (C_PISO_FRAC + (1 - C_PISO_FRAC) * min(1.0, (t / sesgo) ** 0.7))
        salida.append(oklch_a_hex(L, C, HUE_BASE + (HUE_PELIGRO - HUE_BASE) * t))
    return salida


ROJA = rampa(5)
for i, hex_ in enumerate(ROJA):
    L, C, _ = oklch(hex_)
    print(f"  clase {i + 1}  {hex_}  L={L:.3f}  C={C:.3f}")

# Comprobaciones de una rampa SECUENCIAL: luminosidad monótona y saltos
# perceptibles. No se exige el 2:1 del extremo claro (eso es para escalas
# ordinales): en una secuencial el paso más claro significa "casi cero". Lo que
# sí debe cumplirse es que no se confunda con el gris de "sin datos".
Ls = [oklch(h)[0] for h in ROJA]
dL = [Ls[i] - Ls[i + 1] for i in range(len(Ls) - 1)]
dE_gris = deltaE(ROJA[0], SIN_DATOS)
print(f"\\n  L monótona decreciente: {all(d > 0 for d in dL)}")
print(f"  salto de L mínimo:      {min(dL):.4f}   (>= 0.06)")
print(f"  claro vs sin datos:     dE {dE_gris:.1f}  (>= 8)")
print(f"  variación de tono:      {HUE_PELIGRO - HUE_BASE:.1f}°  (un solo tono)")
assert all(d > 0 for d in dL) and min(dL) >= 0.06 and dE_gris >= 8"""),

("code", """CORTES = [0, 500, 1_500, 3_000, 8_000, np.inf]
ETIQUETAS = ["< 500", "500 – 1.500", "1.500 – 3.000", "3.000 – 8.000", "> 8.000"]
TINTA, TINTA_2, FONDO = "#0b0b0b", "#52514e", "#fcfcfb"


def clase_de(valor, cortes):
    \"\"\"Índice de la clase a la que cae un valor, según los cortes.\"\"\"
    for i in range(len(cortes) - 1):
        if cortes[i] <= valor < cortes[i + 1]:
            return i
    return len(cortes) - 2


# Los desplazamientos de las etiquetas van en METROS, así que hay que proyectar
# antes de anotar. En lat/lon un "900" serían 900 grados y las etiquetas
# saldrían disparadas fuera del mapa.
mapa = barrios.to_crs(9377).copy()
mapa["clase"] = mapa["tasa"].map(lambda v: clase_de(v, CORTES))


def dibujar(columna_clase, etiquetas, titulo, subtitulo, anotar=()):
    fig, ax = plt.subplots(figsize=(9.5, 11), facecolor=FONDO)
    ax.set_facecolor(FONDO)
    mapa.plot(ax=ax, color=SIN_DATOS, edgecolor=FONDO, linewidth=0.4)
    for i in range(len(etiquetas)):
        sub = mapa[mapa[columna_clase] == i]
        if len(sub):
            sub.plot(ax=ax, color=ROJA[i], edgecolor=FONDO, linewidth=0.4)

    # Cada etiqueta se corre hacia afuera con su propio desplazamiento, para
    # que dos barrios vecinos del centro no queden encimados.
    for codigo, (dx, dy) in anotar:
        if codigo not in mapa.index:
            continue
        fila = mapa.loc[codigo]
        punto = fila.geometry.representative_point()
        ax.annotate(fila["nombre"], (punto.x + dx, punto.y + dy), fontsize=8.5,
                    fontweight="bold", color=TINTA, ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.22", facecolor=FONDO,
                              edgecolor="none", alpha=0.82))

    ax.set_title(titulo, loc="left", fontsize=15, fontweight="bold",
                 color=TINTA, pad=20)
    ax.text(0, 1.006, subtitulo, transform=ax.transAxes, fontsize=9.5,
            color=TINTA_2, va="bottom")
    ax.set_axis_off()

    parches = [mpatches.Patch(facecolor=ROJA[i], edgecolor="#ffffff",
                              linewidth=0.8, label=e)
               for i, e in enumerate(etiquetas)]
    parches.append(mpatches.Patch(facecolor=SIN_DATOS, edgecolor="#ffffff",
                                  linewidth=0.8, label="Sin datos"))
    leg = ax.legend(handles=parches, loc="lower left", frameon=True, fontsize=9,
                    title="Hurtos por 100.000 hab. y por año", title_fontsize=9.5)
    leg.get_frame().set_facecolor(FONDO)
    leg.get_frame().set_edgecolor("#e1e0d9")
    fig.text(0.02, 0.012, "Fuente: MEData, Alcaldía de Medellín · hurtos "
             "2018–2022 · población 2021 · barrios con ≥ 2.000 habitantes",
             fontsize=8, color="#898781")
    plt.show()


dibujar("clase", ETIQUETAS, "Dónde ocurre el hurto en Medellín",
        "Tasa de hurto por barrio, todos los tipos. Más rojo, más hurtos por "
        "habitante. El rojo está en el centro y el sur, no en la periferia.",
        anotar=[("1019", (900, -1500)), ("1013", (1500, -300)), ("1422", (0, 0)),
                ("1003", (700, 1600)), ("1107", (-1900, 0)), ("1018", (1500, 1300))])"""),

("md", """### El mismo mapa, para el hurto a la casa

El hurto **a persona** ocurre en vía pública (45% de los casos): lo sufre quien
transita. El hurto **a residencia** lo sufre quien vive ahí. Si el primero dice
dónde hay que cuidar la calle, el segundo dice dónde hay que cuidar la casa.

Cuando se separan, el mapa cambia de forma."""),

("code", """CORTES_R = [0, 75, 150, 300, 550, np.inf]
ETIQ_R = ["< 75", "75 – 150", "150 – 300", "300 – 550", "> 550"]
mapa["clase_r"] = mapa["tasa_residencia"].map(lambda v: clase_de(v, CORTES_R))

dibujar("clase_r", ETIQ_R, "Dónde se roban las casas",
        "Hurto a residencia por barrio, 2018-2022: el riesgo de quien vive ahí. "
        "La escala es diez veces menor que la del hurto en la calle.",
        anotar=[("1407", (1400, 0)), ("1211", (-2200, 0)), ("1113", (1200, 700)),
                ("1112", (-1600, -1200)), ("1202", (-1800, 900)),
                ("1602", (-2600, -400))])"""),

("md", """---

## 4. ¿Se agrupa en el mapa?

El **I de Moran** de la sesión 6: ¿los barrios con tasa parecida están juntos?

| Variable | I de Moran | Lectura |
|---|---|---|
| Hurto total | 0,20 | agrupación débil |
| Hurto en la calle | 0,19 | agrupación débil |
| **Hurto a residencia** | **0,69** | agrupación fuerte |

La diferencia es el hallazgo. El hurto **en la calle** es de oportunidad: depende
de dónde pasa la gente, y eso no respeta linderos. El hurto **a la casa** depende
del barrio mismo, y ahí sí hay zonas enteras con el mismo problema.

Para la política: el hurto en la calle pide **patrullaje por corredores** (que
cruza barrios); el hurto a la casa pide **intervención por zona**."""),

("code", """w = Queen.from_dataframe(barrios, use_index=True)
w.transform = "r"

for col in ["tasa", "tasa_calle", "tasa_residencia"]:
    m = Moran(barrios[col], w)
    print(f"  {col:<18} I = {m.I:6.3f}   p = {m.p_sim:.3f}")

local = Moran_Local(barrios["tasa"], w, seed=0)
barrios["cuadrante"] = pd.Series(local.q, index=barrios.index).map(
    {1: "Alto-Alto", 2: "Bajo-Alto", 3: "Bajo-Bajo", 4: "Alto-Bajo"})
barrios.loc[local.p_sim >= 0.05, "cuadrante"] = "No significativo"

print()
print(barrios.groupby("cuadrante").agg(
    barrios=("nombre", "count"), poblacion=("poblacion", "sum"),
    hurtos=("total", "sum")).to_string())"""),

("md", """Los **14 barrios Alto-Alto** (hurto alto rodeado de hurto alto) son el centro y
Laureles. Concentran **47.205 hurtos con 98.512 habitantes** — una cuarta parte del
total de la ciudad en el 4% de la población.

Los **56 Bajo-Bajo** son la periferia: 638.863 personas y solo 13.310 hurtos."""),

("md", """---

## 5. De dónde sale la política: lugar, modalidad y hora

Un mapa dice **dónde**. Para saber **qué hacer** hay que abrir el hurto a persona,
que es el 77% del total.

**Dónde ocurre** (2018–2022):

| Lugar | Casos |
|---|---|
| Vía pública | 83.479 |
| Estación del Metro | 10.134 |
| Almacén o tienda | 9.601 |
| Residencia | 6.386 |
| Bus de servicio público | 5.407 |
| Centro comercial | 5.064 |

**Cómo ocurre:**

| Modalidad | Casos |
|---|---|
| Atraco | 94.529 |
| Descuido | 34.105 |
| Cosquilleo | 27.187 |
| Raponazo | 10.865 |

**Con qué:** sin arma 92.106; arma de fuego 48.848; arma cortopunzante 32.282.

**A qué hora:** el pico va de **17h a 20h** (10.737 casos a las 18h), justo la
salida laboral. El mínimo es 23h–03h."""),

("code", """persona = pd.read_csv(ARCHIVOS["persona"], dtype=str, low_memory=False,
                      usecols=["fecha_hecho", "lugar", "modalidad", "arma_medio"])
persona["fecha"] = pd.to_datetime(persona["fecha_hecho"], errors="coerce")
persona = persona[persona["fecha"].dt.year.between(ANIO_INI, ANIO_FIN)]

print(f"Hurto a persona 2018-2022: {len(persona):,}\\n")
for columna, titulo in [("lugar", "LUGAR"), ("modalidad", "MODALIDAD"),
                        ("arma_medio", "ARMA")]:
    print(f"=== {titulo} ===")
    print(persona[columna].value_counts().head(6).to_string())
    print()"""),

("code", """horas = persona["fecha"].dt.hour.value_counts().sort_index()

fig, ax = plt.subplots(figsize=(10, 4), facecolor=FONDO)
ax.bar(horas.index, horas.values, color=ROJA[3], width=0.72)
ax.set_xticks(range(0, 24))
ax.set_xlabel("Hora del día")
ax.set_ylabel("Hurtos a persona")
ax.set_title("El hurto a persona sigue el horario de la ciudad",
             loc="left", fontweight="bold", pad=28)
ax.text(0, 1.015, "2018-2022. El pico va de 17h a 20h: la salida laboral.",
        transform=ax.transAxes, fontsize=9.5, color=TINTA_2, va="bottom")
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", color="#e1e0d9", linewidth=0.8)
ax.set_axisbelow(True)
plt.show()"""),

("md", """---

## 6. Las políticas

El patrón manda. Cuatro hallazgos, cuatro instrumentos distintos.

### A. El hurto es de oportunidad y sigue el horario laboral

Atraco (51,2%) y descuido (18,5%) dominan; el pico es 17h–20h; el 45,2% ocurre en
vía pública. **No es un delito de noche en callejones: es un delito de hora pico en
corredores concurridos.**

- **Patrullaje por corredores, no por cuadrante.** Reforzar 16h–21h en los ejes
  comerciales y de transporte, no repartir la fuerza por área.
- **Cámaras y alumbrado en los nodos de transporte.** Estación del Metro es el
  segundo lugar (10.134 casos): es un punto fijo, concentrado y predecible.

### B. El centro y Laureles son el problema, no la periferia

La Candelaria tiene **11.398** hurtos por 100.000 hab/año; Popular y Santa Cruz,
**369**. Una diferencia de **31 veces**.

- **El presupuesto de seguridad debe seguir al delito, no a la pobreza.** Hoy el
  reflejo es mandar más policía a la periferia. Los datos dicen lo contrario.
- **Pero cuidado con la lectura fácil.** Los barrios ricos tienen más hurto
  *reportado*: hay más que robar, más denuncia y más seguros. Parte de la brecha
  es de reporte, no de delito. Antes de mover recursos, hay que medir la
  subdenuncia en la periferia.

### C. El hurto a la casa es un problema de zona

Con I de Moran de **0,69**, el hurto a residencia se agrupa. Los diez barrios con
más hurto a la casa forman un corredor continuo del occidente: Las Lomas No. 1 y
No. 2 (El Poblado), Simón Bolívar y Calasanz (La América), Estadio, El Velódromo,
Florida Nueva y Bolivariana (Laureles), Rosales (Belén) y La Candelaria.

- **Intervención por zona, no por barrio.** La sesión 6 ya enseñó que las islas de
  carencia cruzan límites de comuna. Aquí pasa lo mismo: la zona de hurto
  residencial cruza El Poblado, Laureles, La América y Belén.
- **Prevención situacional:** portería, alumbrado, diseño de accesos, alarmas
  comunitarias. Es un delito de acceso, no de calle.

### D. El hurto no se reparte como la carencia

Este es el punto de política más importante, y el que conecta con la sesión 6:

| Problema | Dónde se concentra | Instrumento |
|---|---|---|
| **Carencia urbana** | periferia pobre (Manrique, Popular) | vivienda, servicios, espacio público |
| **Hurto** | centro y sur ricos (Candelaria, Laureles) | prevención situacional, patrullaje |

**Son dos políticas distintas y no compiten por el mismo peso.** Repartir el
Presupuesto Participativo con un índice de carencia y el de seguridad con un mapa
de delito es correcto. Lo incorrecto sería usar uno para justificar el otro.

### Lo que estos datos no pueden decir

- **Subdenuncia.** Una tasa baja puede ser un barrio seguro o un barrio donde no se
  denuncia. Los datos son de denuncia, no de delito.
- **Población flotante.** El Poblado, Guayaquil y La Candelaria reciben mucha más
  gente de la que registran. Su tasa está inflada.
- **El móvil del delito.** No se puede separar el hurto del habitante del hurto del
  visitante.
- **2023 quedó fuera** (llega a noviembre) y `hurto a establecimiento` se corta en
  2017."""),

("md", """---

## 7. Exportar

Guardamos la tabla por barrio en `datalake/data/processed/hurto/`, con los mismos
cuidados de la sesión 6: coordenadas en lat/lon (EPSG:4326) y sin tildes ni
espacios en los nombres de columna. Se guarda **también un CSV**: un mapa nunca
debe ser la única forma de leer un dato."""),

("code", """SALIDA.mkdir(parents=True, exist_ok=True)

cols = ["nombre", "comuna", "poblacion", "pct_estrato_1_2", *TIPOS,
        "total", "tasa", "tasa_calle", "tasa_residencia", "cuadrante", "geometry"]
tabla = barrios[cols].reset_index().to_crs(4326)
tabla.to_file(SALIDA / "barrios_hurto.geojson")
tabla.drop(columns="geometry").sort_values("tasa", ascending=False).to_csv(
    SALIDA / "tabla_hurto_barrio.csv", index=False, encoding="utf-8")
print(f"Exportados {len(tabla)} barrios a {SALIDA}")"""),

("md", """---

## Resumen de la sesión

| Tema | Herramientas clave |
|---|---|
| Datos | 6 conjuntos de MEData, `pd.to_datetime()`, filtrar por año |
| Agregar | `groupby()`, `lstrip("#")` en el código de barrio, join contra el geojson |
| Tasas | dividir por población y por años; el sesgo del denominador |
| Color | rampa secuencial de un tono en OKLCH, luminosidad monótona, gris para "sin datos" |
| Comparar mapas | una escala por vista; el mismo dato con otra escala cuenta otra historia |
| Agrupación | `Queen.from_dataframe()`, `Moran()`, `Moran_Local()` |
| Política | cruzar lugar × modalidad × hora para pasar del dónde al qué |

**Respuestas del caso:** el hurto en Medellín **no** se concentra en la periferia
pobre, sino en el centro y el sur ricos (ρ = −0,86 con el estrato). La Candelaria
tiene 31 veces la tasa de Popular. El hurto en la calle es de oportunidad y sigue
el horario laboral (pico 17h–20h, 45% en vía pública); el hurto a la casa sí se
agrupa en el mapa (I = 0,69) y pide intervención por zona. Carencia urbana y hurto
son dos mapas distintos y piden dos políticas distintas.

---

## Preguntas de discusión — cierre

1. Vuelvan a la pregunta 1 del inicio. Después de ver los datos, ¿sigue en pie su
   respuesta? ¿Qué la cambiaría?
2. El mapa de hurto y el de carencia urbana son casi opuestos. Si tuvieran que
   explicarle a una junta de acción comunal de Manrique por qué su barrio tiene
   poca prioridad en seguridad pero mucha en vivienda, ¿qué les dirían?
3. La subdenuncia puede explicar parte de la brecha. ¿Cómo la medirían con los
   datos que tienen? ¿Qué fuente pedirían?"""),
]


def main() -> None:
    celdas = []
    for i, (tipo, texto) in enumerate(CELDAS):
        # nbformat solo admite 'markdown', 'code' y 'raw'. Con 'md' el archivo
        # es JSON valido pero Jupyter no dibuja la celda.
        tipo = "markdown" if tipo == "md" else tipo
        celda = {
            "cell_type": tipo,
            "id": f"celda-{i:02d}",
            "metadata": {},
            "source": texto.splitlines(keepends=True),
        }
        if tipo == "code":
            celda["execution_count"] = None
            celda["outputs"] = []
        celdas.append(celda)

    nb = {
        "cells": celdas,
        "metadata": {"kernelspec": KERNEL, "language_info": LANGINFO},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    destino = AQUI / "07_hurto_por_barrio.ipynb"
    destino.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Escrito {destino.name}: {len(celdas)} celdas")


if __name__ == "__main__":
    main()
