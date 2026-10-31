"""Genera y valida la rampa secuencial roja del mapa de hurto.

Regla del metodo: secuencial = un solo tono, claro -> oscuro, luminosidad
monotona decreciente. El rojo aqui es calor semantico (peligro), con leyenda
de escala, que es una de las dos excepciones multi-tono permitidas.

Un rojo que solo pierde croma al oscurecerse termina pardo (#684140), no rojo.
Por eso la croma sube hasta C_pico y ahi se mantiene, y el tono se corre un
poco hacia el rojo puro en los pasos oscuros: el barrio mas peligroso recibe
el rojo mas intenso, que es justo lo que el lector debe ver.

El modulo se basta a si mismo: la matematica OKLab esta aqui abajo. Si el
validador del skill de visualizacion esta disponible se usa ese, para que la
comprobacion sea la oficial y no una reimplementacion; si no, se cae a las
funciones locales, que dan el mismo resultado. El notebook tiene que correr en
el computador de cualquier estudiante, sin depender de una ruta temporal.
"""
import math

# --------------------------------------------------------------------------
# Conversion de color. OKLab es el espacio de trabajo porque sus distancias se
# parecen a lo que el ojo percibe: en sRGB, dos colores con la misma distancia
# numerica pueden verse identicos o completamente distintos.
# --------------------------------------------------------------------------


def _srgb_a_lineal(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def lin(h):
    """hex -> sRGB lineal (0..1)."""
    h = h.lstrip("#")
    return tuple(_srgb_a_lineal(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))


def linear_to_srgb(c):
    v = 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055
    return max(0, min(255, round(255 * v)))


def lin_srgb_to_oklab(r, g, b):
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (x ** (1 / 3) if x >= 0 else -((-x) ** (1 / 3)) for x in (l, m, s))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def oklab_to_lin_srgb(L, a, bb):
    l_ = L + 0.3963377774 * a + 0.2158037573 * bb
    m_ = L - 0.1055613458 * a - 0.0638541728 * bb
    s_ = L - 0.0894841775 * a - 1.2914855480 * bb
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (+4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def oklch_to_hex(L, C, H):
    a = C * math.cos(math.radians(H))
    bb = C * math.sin(math.radians(H))
    return "#{:02x}{:02x}{:02x}".format(
        *[linear_to_srgb(v) for v in oklab_to_lin_srgb(L, a, bb)])


def oklch(h):
    """hex -> (L, C, H). H en grados."""
    L, a, bb = lin_srgb_to_oklab(*lin(h))
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def deltaE(a, b):
    """Distancia en OKLab x100. Regla practica: < 8 no se distingue."""
    La, aa, ba = lin_srgb_to_oklab(*lin(a))
    Lb, ab, bb = lin_srgb_to_oklab(*lin(b))
    return 100 * math.sqrt((La - Lb) ** 2 + (aa - ab) ** 2 + (ba - bb) ** 2)


def contraste(a, b):
    """Razon de contraste WCAG entre dos colores."""
    def luminancia(h):
        r, g, bl = lin(h)
        return 0.2126 * r + 0.7152 * g + 0.0722 * bl
    la, lb = luminancia(a), luminancia(b)
    alto, bajo = max(la, lb), min(la, lb)
    return (alto + 0.05) / (bajo + 0.05)


# Si el validador oficial esta en el disco, se usan su contraste y su deltaE,
# que son la referencia del metodo. `oklch` no se toma de ahi: el oficial
# devuelve solo (L, C) y aqui hace falta tambien el tono, que calcula el local.
try:
    import sys as _sys
    _sys.path.insert(0, r"C:\Users\ASUS\AppData\Local\Temp\claude\bundled-skills"
                            r"\2.1.310\30ef5280d4e9e5ffb165ff952ce99a3f\dataviz\scripts")
    from validate_palette import contrast as contraste  # noqa: F811
    from validate_palette import deltaE as deltaE  # noqa: F811

    VALIDADOR = "oficial"
except ImportError:
    VALIDADOR = "local"


def hex_to_hue(h):
    """Tono OKLCH de un hex del palette.md, para no inventar un tono nuevo."""
    return oklch(h)[2]


HUE_BASE = hex_to_hue("#e34948")     # rojo categorico
HUE_PELIGRO = 29.0                    # rojo puro al que se corre el extremo oscuro
C_PISO_FRAC = 0.30                    # croma minima del paso mas claro (no gris)
SIN_DATOS = "#b8b8b8"                 # gris neutro, fuera de la rampa


def rampa(pasos=5, L_ini=0.96, L_fin=0.45, C_pico=0.20, sesgo=0.55):
    """Rampa de un tono, claro -> oscuro, de `pasos` colores.

    L_ini arranca en 0.96 y no mas claro: el paso mas claro tiene que seguir
    leyendose como un color y no confundirse con el gris de "sin datos", que es
    un canal aparte. L_fin en 0.45 deja el extremo oscuro bien oscuro sin
    volverse negro, donde ya no se distinguiria del texto.
    """
    salida = []
    for i in range(pasos):
        t = i / (pasos - 1)
        L = L_ini + (L_fin - L_ini) * t
        # La croma arranca en un piso (C_PISO_FRAC) y sube rapido: sin ese piso
        # el paso mas claro sale gris puro y se confunde con "sin datos".
        C = C_pico * (C_PISO_FRAC + (1 - C_PISO_FRAC) * min(1.0, (t / sesgo) ** 0.7))
        salida.append(oklch_to_hex(L, C, HUE_BASE + (HUE_PELIGRO - HUE_BASE) * t))
    return salida


PASOS = 5
ROJA = rampa(PASOS)


def validar(rampa_, superficie="#fcfcfb"):
    """Comprobaciones de una rampa SECUENCIAL (choropleth de magnitud).

    No se aplica la regla ordinal del extremo claro >= 2:1: en una escala
    secuencial el paso mas claro significa "casi cero" y puede acercarse al
    fondo. Lo que si debe cumplirse es que el paso mas claro NO se confunda con
    el gris de "sin datos": ese es el unico limite que importa aqui, porque el
    gris es un canal distinto y no un valor de la escala.
    """
    Ls = [oklch(h)[0] for h in rampa_]
    dL = [Ls[i] - Ls[i + 1] for i in range(len(Ls) - 1)]
    fallos = []
    if not all(d > 0 for d in dL):
        fallos.append("L no es monotona decreciente")
    if min(dL) < 0.06:
        fallos.append(f"salto de L adyacente {min(dL):.4f} < 0.06")
    # El paso mas claro contra el gris de "sin datos": deben ser distinguibles.
    dE_gris = deltaE(rampa_[0], SIN_DATOS)
    if dE_gris < 8.0:
        fallos.append(f"paso mas claro a dE {dE_gris:.1f} del gris sin datos (< 8)")
    return {"Ls": Ls, "dL": dL, "dE_gris": dE_gris, "fallos": fallos}


if __name__ == "__main__":
    print(f"Validador: {VALIDADOR}")
    print(f"Hue base (de #e34948): {HUE_BASE:.1f}  ->  peligro: {HUE_PELIGRO}")
    print(f"\nRampa de {PASOS} clases (claro = menos hurtos, oscuro = mas):")
    for i, h in enumerate(ROJA):
        L, C = oklch(h)[:2]
        print(f"  clase {i + 1}  {h}  L={L:.3f}  C={C:.3f}  "
              f"contraste vs claro={contraste(h, '#fcfcfb'):.2f}")

    v = validar(ROJA)
    print(f"\n  L monotona decreciente: {all(d > 0 for d in v['dL'])}")
    print(f"  dL adyacente minimo:    {min(v['dL']):.4f}   (>= 0.06 requerido)")
    print(f"  tono unico:             variacion de tono "
          f"{max(HUE_BASE, HUE_PELIGRO) - min(HUE_BASE, HUE_PELIGRO):.1f} grados")
    print(f"  claro vs sin datos:     dE {v['dE_gris']:.1f}  (>= 8 requerido)")
    print(f"  sin datos:              {SIN_DATOS}  (gris, fuera de la rampa)")

    if v["fallos"]:
        print("\n  FALLOS: " + "; ".join(v["fallos"]))
        raise SystemExit(1)
    print("\n  Todas las comprobaciones de la rampa pasan.")
