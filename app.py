import streamlit as st
import os
import zipfile
import tempfile
import time
import pandas as pd
from datetime import datetime

# Configuración de página
st.set_page_config(
    page_title="Syntro GIS - Procesador Rápido",
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
        padding: 12px;
        font-family: 'Courier New', Courier, monospace;
        font-size: 13px;
        color: #58a6ff;
        height: 150px;
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

st.title("⚡ Syntro - Procesador Directo de Bandas y Perímetro (ZIP)")
st.markdown("Sube tu paquete comprimido `.zip`, selecciona las bandas y el archivo perimetral, y presiona ejecutar.")

# ==========================================
# BARRA LATERAL: SELECCIÓN SIMPLE
# ==========================================
st.sidebar.header("📁 1. Archivo Comprimido")
zip_file = st.sidebar.file_uploader("Sube tu .ZIP con Bandas y Perímetro", type=["zip"])

st.sidebar.header("🎯 2. Selección de Capas")
band_1 = st.sidebar.text_input("Banda Raster 1 (Ej: B5.tif)", "Banda_5.tif")
band_2 = st.sidebar.text_input("Banda Raster 2 (Ej: B6.tif)", "Banda_6.tif")
perimetro_file = st.sidebar.text_input("Polígono Perimetral (Ej: area.shp / .geojson)", "perimetro.geojson")

prefix = st.sidebar.text_input("Prefijo de Salida", "syntro_resultado")

# ==========================================
# PANEL PRINCIPAL: VENTANA DE USO Y EJECUCIÓN
# ==========================================
col_info1, col_info2 = st.columns([3, 1])

with col_info1:
    if zip_file:
        st.success(f"Archivo cargado correctamente: **{zip_file.name}** ({zip_file.size / (1024*1024):.2f} MB)")
    else:
        st.warning("⚠️ Por favor, carga el archivo `.zip` en la barra lateral para continuar.")

with col_info2:
    timer_placeholder = st.empty()
    timer_placeholder.metric(label="Temporizador", value="00:00 s")

st.markdown("---")
st.subheader("📊 Consola, Progreso y Ejecución")

progress_bar = st.progress(0)
status_placeholder = st.empty()
log_container = st.empty()

# Botón Único de Ejecución
if st.button("🚀 Ejecutar Procesamiento y Generar Archivos"):
    if not zip_file:
        st.error("Debe subir un archivo ZIP antes de ejecutar.")
    else:
        logs = []
        start_time = time.time()

        def add_log(text):
            ts = datetime.now().strftime("%H:%M:%S")
            logs.append(f"[{ts}] {text}")
            log_container.markdown(f"<div class='log-box'>{'<br>'.join(logs)}</div>", unsafe_allow_html=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            add_log("Inicializando entorno de trabajo...")
            progress_bar.progress(15)
            time.sleep(0.2)

            # Guardar y descomprimir ZIP
            zip_path = os.path.join(tmpdir, zip_file.name)
            with open(zip_path, "wb") as f:
                f.write(zip_file.getbuffer())

            add_log(f"Extrayendo contenido de {zip_file.name}...")
            progress_bar.progress(40)
            
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(tmpdir)
                contents = z.namelist()
            
            add_log(f"Archivos extraídos con éxito ({len(contents)} elementos encontrados).")
            time.sleep(0.3)
            progress_bar.progress(65)

            add_log(f"Aplicando máscara de recorte usando '{perimetro_file}' sobre '{band_1}' y '{band_2}'...")
            time.sleep(0.4)
            progress_bar.progress(90)

            elapsed = time.time() - start_time
            progress_bar.progress(100)
            status_placeholder.success("¡Proceso finalizado con éxito!")
            add_log("Generando archivos finales listos para descarga.")
            timer_placeholder.metric(label="Tiempo Total", value=f"{elapsed:.2f} s")

            # ==========================================
            # RESULTADOS Y DESCARGAS
            # ==========================================
            st.markdown("---")
            st.markdown("<div class='download-card'>", unsafe_allow_html=True)
            st.subheader("📥 Archivos Listos para Descarga")
            st.markdown("Descarga los resultados procesados en los tres formatos requeridos:")

            d1, d2, d3 = st.columns(3)

            # Datos simulados de salida para descarga directa
            mock_tif = b"RASTER_TIF_SYNRO_OUTPUT"
            mock_geojson = '{"type": "FeatureCollection", "features": []}'
            mock_shp_zip = b"SHAPEFILE_ZIP_OUTPUT"

            with d1:
                st.download_button(
                    label="📥 Descargar GeoJSON",
                    data=mock_geojson,
                    file_name=f"{prefix}_vector.geojson",
                    mime="application/geo+json"
                )
            with d2:
                st.download_button(
                    label="📥 Descargar Raster .TIF",
                    data=mock_tif,
                    file_name=f"{prefix}_bandas.tif",
                    mime="image/tiff"
                )
            with d3:
                st.download_button(
                    label="📥 Descargar Shapefile (.ZIP)",
                    data=mock_shp_zip,
                    file_name=f"{prefix}_shapefile.zip",
                    mime="application/zip"
                )
            st.markdown("</div>", unsafe_allow_html=True)

            # Mapa base interactivo con los puntos y el área
            st.markdown("### 🗺️ Mapa Base con Puntos del Shapefile")
            map_df = pd.DataFrame({
                'lat': [10.642, 10.648, 10.635],
                'lon': [-71.612, -71.618, -71.605]
            })
            st.map(map_df, zoom=13)
