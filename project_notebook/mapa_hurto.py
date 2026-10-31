"""Mapas coropleticos del hurto por barrio.

Escala secuencial de un solo tono (rojo), claro -> oscuro: mas rojo = mas
peligroso. El gris queda reservado para "sin datos", que es un canal distinto
y no un valor de la escala.

Cada vista lleva SU PROPIA escala. El hurto a persona llega a 111.000 por
100.000 habitantes y el hurto a residencia a 908: con cortes compartidos, el
segundo mapa caeria entero en la primera clase y no diria nada. Los cortes se
eligen por vista, sobre los quintiles de esa variable, y siempre redondeados.
"""

import sys
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import project_notebook.rampa as R  # noqa: E402
from project_notebook.hurto_por_barrio import construir  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "datalake" / "data" / "processed" / "hurto"
SALIDA.mkdir(parents=True, exist_ok=True)

TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
TINTA_SUAVE = "#898781"
FONDO = "#fcfcfb"

# Una escala por vista: (columna, cortes, etiquetas, titulo, subtitulo, archivo)
VISTAS = [
    dict(
        columna="tasa",
        cortes=[0, 500, 1_500, 3_000, 8_000, np.inf],
        etiquetas=["<500", "500 – 1.500", "1.500 – 3.000", "3.000 – 8.000", ">8.000"],
        titulo="¿Dónde ocurre el hurto en Medellín?",
        subtitulo="Tasa de hurto por barrio, todos los tipos. Más rojo, más hurtos "
                  "por habitante. El rojo está en el centro y el sur, no en la periferia.",
        archivo="mapa_hurto_total.png",
    ),
    dict(
        columna="tasa_residencia",
        cortes=[0, 75, 150, 300, 550, np.inf],
        etiquetas=["< 75", "75 – 150", "150 – 300", "300 – 550", "> 550"],
        titulo="¿Dónde roban a casas?",
        subtitulo="Hurto a residencia por barrio: el riesgo de quien vive ahí. "
                  "La escala es diez veces menor que la del hurto en la calle.",
        archivo="mapa_hurto_residencia.png",
    ),
]


def clase_de(valor, cortes, etiquetas):
    for i in range(len(cortes) - 1):
        if cortes[i] <= valor < cortes[i + 1]:
            return etiquetas[i]
    return etiquetas[-1]


def dibujar(barrios, vista, anotar=()):
    columna = vista["columna"]
    cortes, etiquetas = vista["cortes"], vista["etiquetas"]

    # Los desplazamientos de las etiquetas van en metros: hay que proyectar. En lat/lon, "900" serian 900 grados y las etiquetas saldrian del mapa.
    barrios = barrios.to_crs(9377).copy()
    barrios["clase"] = barrios[columna].map(lambda v: clase_de(v, cortes, etiquetas))

    fig, ax = plt.subplots(figsize=(9.5, 11), facecolor=FONDO)
    ax.set_facecolor(FONDO)

    # Base del mapa en gris sin datos
    barrios.plot(ax=ax, color=R.SIN_DATOS, edgecolor=FONDO, linewidth=0.4)

    # Capas coloreadas por rango de tasa
    for i, clase in enumerate(etiquetas):
        sub = barrios[barrios["clase"] == clase]
        if len(sub):
            sub.plot(ax=ax, color=R.ROJA[i], edgecolor=FONDO, linewidth=0.4)

    # Etiquetas: se corren hacia afuera con un desplazamiento por barrio, para que dos vecinos del centro no queden encimados.
    for codigo, (dx, dy) in anotar:
        if codigo not in barrios.index:
            continue
        fila = barrios.loc[codigo]
        punto = fila.geometry.representative_point()
        ax.annotate(
            fila["nombre"],
            (punto.x + dx, punto.y + dy),
            fontsize=8.5,
            fontweight="bold",
            color=TINTA,
            ha="center",
            va="center",
                bbox=dict(boxstyle="round,pad=0.22",
                facecolor=FONDO,
                edgecolor="none",
                alpha=0.82
            ),
        )

    ax.set_title(vista["titulo"], loc="left", fontsize=15, fontweight="bold",
                 color=TINTA, pad=20)
    ax.text(
        0,
        1.006,
        vista["subtitulo"],
        transform=ax.transAxes,
        fontsize=9.5,
        color=TINTA_2,
        va="bottom"
    )
    ax.set_axis_off()

    # Formato de leyenda
    parches = [
        mpatches.Patch(
            facecolor=R.ROJA[i], edgecolor="#ffffff", linewidth=0.8, label=e
        )
        for i, e in enumerate(etiquetas)
    ]
    parches.append(
        mpatches.Patch(
            facecolor=R.SIN_DATOS, edgecolor="#ffffff",
                                  linewidth=0.8, label="Sin datos"
        )
    )
    leg = ax.legend(
        handles=parches,
        loc="lower left",
        frameon=True,
        fontsize=9,
        title="Hurtos por 100.000 hab. y por año",
        title_fontsize=9.5
    )
    leg.get_frame().set_facecolor(FONDO)
    leg.get_frame().set_edgecolor("#e1e0d9")
    leg._legend_box.align = "left"

    # Pie de página con la fuente
    fig.text(0.02, 0.012,
           "Fuente: MEData, Alcaldía de Medellín · hurtos 2018–2022 · " "población 2021 · barrios con ≥ 2.000 habitantes",
           fontsize=8, color=TINTA_SUAVE)

    # Carpeta de destino en Windows    
    ruta_guardado = SALIDA / vista["archivo"]    
    ruta_guardado.parent.mkdir(parents=True, exist_ok=True)    

    # Guarda la imagen completa en la carpeta SALIDA    
    fig.savefig(SALIDA / vista["archivo"], dpi=200, bbox_inches="tight")    

    # Figura    
    plt.show()    