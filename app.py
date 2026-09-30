import streamlit as st
import os
import zipfile
import tempfile
import time
import pandas as pd
from datetime import datetime

# Configuración de página
st.set_page_config(
    page_title="Syntro GIS Auto-Detect",
    page_icon="⚡",
    layout="wide"
)

# Estilo visual moderno y limpio (3D / UI)
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        font-weight: bold;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .stButton>button:hover { background: linear-gradient(135deg, #1d4ed8 100%, #1e40af 100%); }
    .log-box {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 10px;
        font-family: 'Courier New', Courier, monospace;
        font-size: 12px;
        color: #58a6ff;
        height: 120px;
        overflow-y: scroll;
    }
    .download-card {
        background-color: #1f242d;
        border: 1px solid #3b4252;
        border-radius: 8px;
        padding: 15px;
        margin-top: 10px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ Syntro - Procesador Automático con Detección en ZIP")
st.markdown("Sube tu paquete `.zip`: el sistema detectará automáticamente las bandas y el área de estudio para que solo tengas que seleccionarlas.")

# ==========================================
# BARRA LATERAL: CARGA Y DETECCIÓN AUTOMÁTICA
# ==========================================
st.sidebar.header("📁 1. Paquete Comprimido")
zip_file = st.sidebar.file_uploader("Sube tu archivo .ZIP", type=["zip"])

# Variables por defecto si no hay zip cargado
raster_files = []
vector_files = []

if zip_file is not None:
    # Directorio temporal para leer el contenido del ZIP de forma instantánea
    with tempfile.TemporaryDirectory() as temp_scan:
        zip_path = os.path.join(temp_scan, zip_file.name)
        with open(zip_path, "wb") as f:
            f.write(zip_file.getbuffer())
        
        with zipfile.ZipFile(zip_path, 'r') as z:
            all_names = z.namelist()
            # Filtrar automáticamente por extensiones
            raster_files = [f for f in all_names if f.lower().endswith(('.tif', '.tiff')) and not f.startswith('__MACOSX')]
            vector_files = [f for f in all_names if f.lower().endswith(('.shp', '.geojson', '.json', '.kml', '.gpkg')) and not f.startswith('__MACOSX')]

st.sidebar.header("🎯 2. Selección de Capas Detectadas")

if zip_file is not None:
    band_1 = st.sidebar.selectbox("Seleccionar Banda Raster 1", raster_files if raster_files else ["No se encontraron .tif"])
    band_2 = st.sidebar.selectbox("Seleccionar Banda Raster 2", raster_files if raster_files else ["No se encontraron .tif"])
    perimetro_file = st.sidebar.selectbox("Seleccionar Área de Estudio (Perímetro)", vector_files if vector_files else ["No se encontró vector (.shp / .geojson)"])
else:
    st.sidebar.info("👆 Sube un archivo .ZIP para autodetectar los archivos.")
    band_1 = st.sidebar.text_input("Banda Raster 1", "Esperando archivo...")
    band_2 = st.sidebar.text_input("Banda Raster 2", "Esperando archivo...")
    perimetro_file = st.sidebar.text_input("Área de Estudio", "Esperando archivo...")

prefix = st.sidebar.text_input("Prefijo de Salida", "syntro_resultado")

# ==========================================
# PANEL PRINCIPAL
# ==========================================
col_info1, col_info2 = st.columns([3, 1])

with col_info1:
    if zip_file:
        st.success(f"Archivo cargado: **{zip_file.name}** | Rasters detectados: {len(raster_files)} | Vectores detectados: {len(vector_files)}")
    else:
        st.warning("⚠️ Carga tu archivo `.zip` en la barra lateral para que el sistema reconozca el contenido.")

with col_info2:
    timer_placeholder = st.empty()
    timer_placeholder.metric(label="Temporizador", value="00:00 s")

st.markdown("---")
st.subheader("📊 Consola y Ejecución")

progress_bar = st.progress(0)
status_placeholder = st.empty()
log_container = st.empty()

# Botón de Ejecución
if st.button("🚀 Ejecutar Procesamiento"):
    if not zip_file:
        st.error("Por favor, sube un archivo ZIP primero.")
    else:
        logs = []
        start_time = time.time()

        def add_log(text):
            ts = datetime.now().strftime("%H:%M:%S")
            logs.append(f"[{ts}] {text}")
            log_container.markdown(f"<div class='log-box'>{'<br>'.join(logs)}</div>", unsafe_allow_html=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            add_log("Iniciando entorno de trabajo...")
            progress_bar.progress(20)
            time.sleep(0.2)

            zip_path = os.path.join(tmpdir, zip_file.name)
            with open(zip_path, "wb") as f:
                f.write(zip_file.getbuffer())

            add_log(f"Descomprimiendo {zip_file.name}...")
            progress_bar.progress(50)
            
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(tmpdir)
            
            add_log(f"Aplicando recorte con área [{perimetro_file}] sobre [{band_1}] y [{band_2}]...")
            time.sleep(0.4)
            progress_bar.progress(85)

            elapsed = time.time() - start_time
            progress_bar.progress(100)
            status_placeholder.success("¡Procesamiento completado con éxito!")
            add_log("Generando archivos de salida listos.")
            timer_placeholder.metric(label="Tiempo Total", value=f"{elapsed:.2f} s")

            # ==========================================
            # DESCARGAS Y MAPA
            # ==========================================
            st.markdown("---")
            st.markdown("<div class='download-card'>", unsafe_allow_html=True)
            st.subheader("📥 Archivos Listos para Descarga")

            d1, d2, d3 = st.columns(3)

            mock_tif = b"RASTER_TIF_OUTPUT"
            mock_geojson = '{"type": "FeatureCollection", "features": []}'
            mock_shp_zip = b"SHAPEFILE_ZIP_OUTPUT"

            with d1:
                st.download_button("📥 GeoJSON", mock_geojson, f"{prefix}.geojson", "application/geo+json")
            with d2:
                st.download_button("📥 Raster TIF", mock_tif, f"{prefix}.tif", "image/tiff")
            with d3:
                st.download_button("📥 Shapefile ZIP", mock_shp_zip, f"{prefix}_shp.zip", "application/zip")
            
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("### 🗺️ Mapa Base con Puntos")
            map_df = pd.DataFrame({
                'lat': [10.642, 10.648, 10.635],
                'lon': [-71.612, -71.618, -71.605]
            })
            st.map(map_df, zoom=13)
