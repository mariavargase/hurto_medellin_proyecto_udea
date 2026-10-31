"""Ejecuta las celdas de codigo del notebook y guarda las figuras.

No hay nbconvert instalado, asi que se hace a mano: cada celda de codigo se
compila y se ejecuta en un espacio de nombres compartido (como haria el
kernel), y plt.show se intercepta para volcar cada figura a PNG. Sirve para
comprobar que el notebook corre entero antes de entregarlo.

Corre con el directorio de trabajo puesto en la carpeta de la sesion, que es
lo que hace Jupyter: el notebook usa Path.cwd().parents[1] para llegar al
datalake.
"""
import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

AQUI = Path(__file__).resolve().parent
os.chdir(AQUI)
DESTINO = AQUI / "_figuras"
contador = {"n": 0}


def mostrar(*_args, **_kwargs):
    contador["n"] += 1
    ruta = DESTINO / f"figura_{contador['n']:02d}.png"
    plt.gcf().savefig(ruta, dpi=110, bbox_inches="tight", facecolor="#fcfcfb")
    plt.close("all")
    print(f"    [figura -> {ruta.name}]")


plt.show = mostrar

nb = json.loads((AQUI / "07_hurto_por_barrio.ipynb").read_text(encoding="utf-8"))
espacio = {"__name__": "__main__"}
DESTINO.mkdir(exist_ok=True)

for i, celda in enumerate(nb["cells"]):
    if celda["cell_type"] != "code":
        continue
    codigo = "".join(celda["source"])
    print(f"\n=== celda {i} ===")
    try:
        exec(compile(codigo, f"<celda {i}>", "exec"), espacio)
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(f"\nFALLO en la celda {i}")
print(f"\nOK: {contador['n']} figuras en {DESTINO}")
