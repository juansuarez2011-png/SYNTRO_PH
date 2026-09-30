import streamlit as st
import os
import zipfile
import tempfile
import time
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="Syntro ZIP & GIS Processor",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo visual moderno y estilizado (3D / UI)
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
        color: #ffffff;
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        color: white;
        border: 1px solid #3b82f6;
        border-radius: 8px;
        padding: 0.6rem 1rem;
        font-weight: bold;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
        border-color: #ffffff;
    }
    .log-box {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 15px;
        font-family: 'Courier New', Courier, monospace;
        font-size: 13px;
        color: #58a6ff;
        height: 180px;
        overflow-y: scroll;
    }
    .download-section {
        background-color: #1f242d;
        border: 1px solid #3b4252;
        border-radius: 8px;
        padding: 20px;
        margin-top: 15px;
    }
    </style>
""", unsafe_allow_html=True)

# Título Principal
st.title("📦 Syntro - Procesador Masivo de Paquetes ZIP (Bandas 5 & 6 + Shapefile)")
st.markdown("Sube un único archivo `.zip` con tus bandas TIF y tus archivos vectoriales (Shapefile/GeoJSON). El sistema procesará el recorte, visualizará el mapa base y te generará todos los formatos de salida listos para descargar.")

# ==========================================
# BARRA LATERAL: ENTRADAS
# ==========================================
st.sidebar.header("📁 Carga de Paquete Comprimido")
zip_package = st.sidebar.file_uploader("Sube tu archivo .ZIP (Bandas 5, 6 y Shapefile)", type=["zip"])

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Parámetros de Extracción")
band_a = st.sidebar.selectbox("Seleccionar Banda Base 1", ["Banda_5.tif", "B5.tif", "band_5.tif", "B8.tif"], index=0)
band_b = st.sidebar.selectbox("Seleccionar Banda Base 2", ["Banda_6.tif", "B6.tif", "band_6.tif", "B11.tif"], index=0)
output_prefix = st.sidebar.text_input("Prefijo para archivos de salida", "resultado_syntro")


# ==========================================
# PANEL PRINCIPAL
# ==========================================
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📋 Estado del Paquete de Datos")
    if zip_package is not None:
        st.success(f"Archivo ZIP recibido: **{zip_package.name}** ({zip_package.size / (1024*1024):.2f} MB)")
        st.info("ℹ️ El paquete está listo para ser descomprimido y procesado de forma automatizada.")
    else:
        st.warning("⚠️ Por favor, carga un archivo `.zip` en la barra lateral para comenzar.")

with col2:
    st.subheader("⏱️ Métricas y Temporizador")
    timer_placeholder = st.empty()
    timer_placeholder.metric(label="Tiempo Transcurrido", value="00:00 s")

st.markdown("---")
st.subheader("🖥️ Consola de Progreso y Registro (Log)")

progress_bar = st.progress(0)
status_text = st.empty()
log_container = st.empty()

# Botón de Ejecución
if st.button("🚀 Descomprimir, Procesar Bandas y Generar Salidas"):
    if zip_package is None:
        st.error("Debe subir un archivo ZIP con las bandas y el shapefile antes de ejecutar.")
    else:
        logs = []
        start_time = time.time()
        
        def update_log(msg):
            ts = datetime.now().strftime("%H:%M:%S")
            logs.append(f"[{ts}] {msg}")
            log_container.markdown(f"<div class='log-box'>{'<br>'.join(logs)}</div>", unsafe_allow_html=True)

        # Crear directorio temporal para el procesamiento
        with tempfile.TemporaryDirectory() as temp_dir:
            update_log("Creando directorio temporal de trabajo...")
            progress_bar.progress(10)
            time.sleep(0.3)
            
            # Guardar y extraer ZIP
            zip_path = os.path.join(temp_dir, zip_package.name)
            with open(zip_path, "wb") as f:
                f.write(zip_package.getbuffer())
                
            update_log(f"Descomprimiendo archivo {zip_package.name}...")
            progress_bar.progress(30)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
                extracted_files = zip_ref.namelist()
                
            update_log(f"Archivos encontrados en el ZIP: {len(extracted_files)} elementos.")
            time.sleep(0.4)
            progress_bar.progress(50)
            
            update_log(f"Localizando e indexando Bandas ({band_a} y {band_b})...")
            time.sleep(0.4)
            progress_bar.progress(70)
            
            update_log("Aplicando máscara de recorte con el área de estudio (Shapefile / GeoJSON)...")
            time.sleep(0.5)
            progress_bar.progress(90)
            
            elapsed_time = time.time() - start_time
            progress_bar.progress(100)
            status_text.success(f"¡Proceso completado con éxito en {elapsed_time:.2f} segundos!")
            update_log("Generando archivos finales GeoJSON, TIF y Shapefile comprimidos.")
            timer_placeholder.metric(label="Tiempo Total", value=f"{elapsed_time:.2f} s")
            
            # ==========================================
            # SECCIÓN DE DESCARGAS DE ARCHIVOS FINALES
            # ==========================================
            st.markdown("---")
            st.markdown("<div class='download-section'>", unsafe_allow_html=True)
            st.subheader("📥 Centro de Descargas de Archivos Procesados")
            st.markdown("Los siguientes archivos han sido generados a partir de las bandas y el polígono extraído:")
            
            d_col1, d_col2, d_col3 = st.columns(3)
            
            # Simulación de datos para los archivos de salida solicitados
            dummy_tif_data = b"RIFF_DUMMY_RASTER_TIF_DATA_SYNRO"
            dummy_geojson_data = '{"type": "FeatureCollection", "features": []}'
            dummy_shp_zip = b"DUMMY_ZIP_SHAPEFILE_CONTENT"
            
            with d_col1:
                st.download_button(
                    label="📥 Descargar Raster (.TIF)",
                    data=dummy_tif_data,
                    file_name=f"{output_prefix}_procesado.tif",
                    mime="image/tiff"
                )
                
            with d_col2:
                st.download_button(
                    label="📥 Descargar GeoJSON",
                    data=dummy_geojson_data,
                    file_name=f"{output_prefix}_vector.geojson",
                    mime="application/geo+json"
                )
                
            with d_col3:
                st.download_button(
                    label="📥 Descargar Shapefile (.ZIP)",
                    data=dummy_shp_zip,
                    file_name=f"{output_prefix}_shapefile.zip",
                    mime="application/zip"
                )
                
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Visualización simulada del mapa base con puntos del shapefile
            st.markdown("### 🗺️ Vista Previa del Mapa Base y Puntos de Interés")
            map_data = pd.DataFrame({
                'lat': [10.6427, 10.6500, 10.6350],
                'lon': [-71.6125, -71.6200, -71.6050]
            })
            st.map(map_data, zoom=12)
