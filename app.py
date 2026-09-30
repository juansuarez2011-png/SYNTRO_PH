import streamlit as st
import os
import tempfile
import time
import pandas as pd
from datetime import datetime

# Configuración de página
st.set_page_config(
    page_title="Syntro GIS - Procesador Independiente",
    page_icon="⚡",
    layout="wide"
)

# Estilo visual moderno y minimalista (3D / UI)
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
        height: 140px;
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

# Encabezado institucional con Logo
col_logo, col_title = st.columns([1, 6])
with col_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=75)
with col_title:
    st.title("⚡ Syntro - Procesador de Bandas & Área de Estudio")
    st.markdown("Carga por separado tu archivo de bandas satelitales y tu polígono de área de estudio perimetral.")

# ==========================================
# BARRA LATERAL: DOS VENTANAS / ENTRADAS INDEPENDIENTES
# ==========================================
st.sidebar.header("📁 1. Archivo de Bandas")
band_file = st.sidebar.file_uploader("Sube el paquete o archivo de bandas (TAR / ZIP / TIF)", type=["tar", "zip", "tif", "tiff"])

st.sidebar.markdown("---")
st.sidebar.header("📁 2. Área de Estudio (Perímetro)")
poly_file = st.sidebar.file_uploader("Sube el perímetro (SHP / KML / GPKG / GeoJSON)", type=["shp", "kml", "gpkg", "geojson", "zip"])

with st.sidebar.expander("⚙️ Parámetros Avanzados"):
    pixel_size = st.number_input("Tamaño de Píxel (m)", min_value=2.0, max_value=30.0, value=10.0, step=1.0)
    target_crs = st.text_input("SRC Destino", value="EPSG:32618")

# ==========================================
# PANEL PRINCIPAL
# ==========================================
col_info1, col_info2 = st.columns([3, 1])

with col_info1:
    b_status = f"✅ Banda cargada: **{band_file.name}**" if band_file else "⚠️ Falta archivo de bandas."
    p_status = f"✅ Perímetro cargado: **{poly_file.name}**" if poly_file else "⚠️ Falta área de estudio."
    
    st.info(f"**Estado de Entradas:**\n- {b_status}\n- {p_status}")

with col_info2:
    timer_placeholder = st.empty()
    timer_placeholder.metric(label="Temporizador", value="00:00 s")

st.markdown("---")
st.subheader("📊 Consola y Ejecución")

progress_bar = st.progress(0)
status_placeholder = st.empty()
log_container = st.empty()

if st.button("🚀 Ejecutar Procesamiento Integrado"):
    if not band_file or not poly_file:
        st.error("Por favor, asegúrate de cargar tanto el archivo de bandas como el área de estudio perimetral.")
    else:
        logs = []
        start_time = time.time()

        def add_log(text):
            ts = datetime.now().strftime("%H:%M:%S")
            logs.append(f"[{ts}] {text}")
            log_container.markdown(f"<div class='log-box'>{'<br>'.join(logs)}</div>", unsafe_allow_html=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            add_log("Iniciando entorno temporal seguro...")
            progress_bar.progress(15)
            time.sleep(0.2)

            add_log(f"Procesando bandas ({band_file.name}) y área perimetral ({poly_file.name})...")
            progress_bar.progress(45)
            time.sleep(0.3)

            add_log(f"Ejecutando recorte espacial y modelo criterial (Resolución: {pixel_size}m, SRC: {target_crs})...")
            progress_bar.progress(80)
            time.sleep(0.5)

            elapsed = time.time() - start_time
            progress_bar.progress(100)
            status_placeholder.success("¡Procesamiento completado con éxito!")
            add_log("Generando reporte técnico HTML, ráster de pH y capas vectoriales de centroides.")
            timer_placeholder.metric(label="Tiempo Total", value=f"{elapsed:.2f} s")

            # ==========================================
            # SECCIÓN DE DESCARGAS Y RESULTADOS
            # ==========================================
            st.markdown("---")
            st.markdown("<div class='download-card'>", unsafe_allow_html=True)
            st.subheader("📥 Paquete de Resultados Listos para Descarga")

            d1, d2, d3 = st.columns(3)

            mock_html = b"<html>Informe Tecnico Syntro pH Estimado</html>"
            mock_tif = b"RASTER_TIF_OUTPUT"
            mock_gpkg = b"GPKG_CENTROIDES_OUTPUT"

            with d1:
                st.download_button("📥 Informe HTML", mock_html, "INFORME_TECNICO_PH.html", "text/html")
            with d2:
                st.download_button("📥 Ráster pH (TIF)", mock_tif, "SYNTRO_PH_EST_PRO.tif", "image/tiff")
            with d3:
                st.download_button("📥 Centroides (GPKG)", mock_gpkg, "SYNTRO_PH_CENTROIDES.gpkg", "application/octet-stream")
            
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("### 🗺️ Visualización Espacial del Área Evaluada")
            map_df = pd.DataFrame({
                'lat': [10.642, 10.648, 10.635],
                'lon': [-71.612, -71.618, -71.605]
            })
            st.map(map_df, zoom=13)
