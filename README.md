# Análisis Espacial del Hurto en Medellín (2018–2022)

Este repositorio contiene el trabajo final para el curso de **Python 3 - Modelos Macroeconómicos (2026)** de la Facultad de Ciencias Económicas de la Universidad de Antioquia.

El proyecto examina la distribución geográfica del hurto en Medellín utilizando datos oficiales de MEData, demostrando que el delito a la propiedad responde a patrones de oportunidad económica y flujo poblacional, en lugar de concentrarse en zonas de vulnerabilidad social.

---

## Integrantes
- **Fernando José Jiménez R.**
   Propuesta del tema y creación del notebook base.
- **María Alejandra Vargas Espinosa**
   Edición, organización, corrección del proyecto y el notebook; creación del informe y exposición del proyecto.
- **Carlos Mario Castro Pérez**

---

## Estructura del Repositorio
- `informe_hurto_medellin.ipynb`: Cuaderno principal con el análisis, mapas y autocorrelación espacial ($I$ de Moran).
- `*informe_proyecto`: Contiene el documento pdf con el informe de una página sobre el proyecto.
- `*.py`: Módulos de Python para la descarga de datos, procesamiento cartográfico y paleta de color OKLCH.

   hurto_medellin_proyecto/             <-- Raíz del repositorio
   ├── .gitignore                       # Filtro para ignorar archivos pesados y temporales
   ├── pyproject.toml                   # Configuración de dependencias para uv sync
   ├── README.md                        # Indicaciones principales del proyecto
   │
   ├── informe_hurto_medellin.ipynb     # Notebook (5 secciones principales según la rúbrica)
   │
   ├── execute.py                       # Módulos y funciones auxiliares de Python
   ├── rampa.py                         # Generación de paleta de color OKLCH
   ├── notebook_construction.py         # Ensamblado de secciones y reportes
   ├── explore.py                       # Funciones de exploración inicial de datos
   ├── export.py                        # Archivos de `geojson` y `csv` en datalake.
   ├── hurto_por_barrio.py              # Agregación y cálculo de tasas por barrio
   ├── mapa_hurto.py                    # Funciones de renderizado cartográfico
   │
   └── datalake/                        # Carpeta local de datos (creada automáticamente)
      ├── data/
      │   ├── raw/medellin/seguridad/  # Capas CSV descargadas de MEData y GeoJSON de barrios
      │   └── processed/hurto/         # Archivos procesados exportados (GeoJSON y CSV)

- `pyproject.toml`: Configuración de dependencias y reproducción del entorno con `uv`.

---

## Instrucciones para Ejecutar

Para reproducir este proyecto en un entorno limpio:

1. Clonar el repositorio:
   ```bash
   git clone <URL_DE_TU_REPOSITORIO>
   cd Hurto_Medellin_Proyecto

2. Sincronizar e instalar las dependencias con `uv`:
   uv sync

3. Abrir JupyterLab:
   uv run jupyter lab

---

## Fuentes de Datos

El análisis utiliza datos abiertos e indicadores oficiales de Medellín.

**No requieren API Key**: los datos se descargan automáticamente a `datalake/data/raw/medellin/` la primera vez que se ejecuta el notebook.

| Fuente | Capa / Conjunto | Registros | Variables Clave |
|---|---|---|---|
| **MEData** | `hurto_a_persona.csv` | 326.489 | Fecha, hora, barrio, lugar, modalidad, arma |
| **MEData** | `hurto_a_residencia.csv` | 42.673 | Fecha, barrio, cantidad |
| **MEData** | `hurto_de_moto.csv` / `carro.csv` | 86.410 / 39.571 | Fecha, barrio, cantidad |
| **MEData** | `pirateria` / `entidad_financiera` | 2.202 / 289 | Fecha, barrio, modalidad |
| **MEData** | `bateria_barrios.csv` | 114 indic. | Población total y por estrato (2021) |
| **Servidor de Mapas UdeA / Medellín** | `barrios.geojson` | 275 polígonos | Polígonos de barrios, código de barrio, comuna |

*Nota:* Se analiza la ventana **2018–2022** (se excluye 2023 por contar con datos parciales hasta noviembre y hurto comercial descontinuado en 2017).

---

## Hallazgos Clave

1. **Sesgo del Denominador:** Para evitar distorsiones en barrios comerciales o industriales con muy pocos residentes nocturnos (como Tenche o sectores de El Poblado), se establece un piso de **≥ 2.000 habitantes**.
2. **Brecha Ricos vs. Pobres:** Los barrios de estratos altos (<20 población en estrato 1 y 2) registran una tasa media de **3.076 hurtos** por 100.000 hab/año, frente a **435 hurtos** en los barrios populares (>80 estrato 1 y 2), reflejando una tasa **7 veces superior** en los sectores de mayores ingresos.
3. **Autocorrelación Espacial (I de Moran):**
   - **Hurto en la Calle (I = 0,19$):** Fenómeno móvil y de oportunidad que sigue las horas pico de desplazamiento laboral (17:00 a 20:00 h).
   - **Hurto a Residencia (I = 0,69$):** Alta concentración espacial que configura un corredor continuo en el occidente de la ciudad (El Poblado, Laureles, Belén, La América).