import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="Syntro GeoProcessor | Panel de Control",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo visual avanzado (Estilo 3D / UI moderna)
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
        color: #ffffff;
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #23272a 0%, #2c2f33 100%);
        color: white;
        border: 1px solid #7289da;
        border-radius: 8px;
        padding: 0.6rem 1rem;
        font-weight: bold;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #7289da 0%, #5865f2 100%);
        border-color: #ffffff;
        box-shadow: 0 6px 8px rgba(114,137,218,0.4);
    }
    .log-box {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 15px;
        font-family: 'Courier New', Courier, monospace;
        font-size: 13px;
        color: #58a6ff;
        height: 200px;
        overflow-y: scroll;
    }
    </style>
""", unsafe_allow_html=True)

# Título principal
st.title("🌍 Syntro - Procesador Geoespacial y Agronómico Automatizado")
st.markdown("Herramienta integral de procesamiento masivo con registro de eventos, control de tiempos y barra de progreso.")

# Barra lateral para configuración de archivos y parámetros
st.sidebar.header("📁 Configuración de Entradas")
uploaded_file = st.sidebar.file_uploader("Seleccione el archivo de entrada (CSV, Excel o Raster/Vectorial)", type=["csv", "xlsx", "txt", "tif", "shp"])

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Parámetros de Proceso")
process_mode = st.sidebar.selectbox("Modo de Análisis", ["Evaluación de Índices de Vegetación", "Modelado Hidrológico SCS", "Procesamiento de Bio-registros"])
output_filename = st.sidebar.text_input("Nombre del archivo de salida", "resultado_syntro.csv")

# Área principal de control
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📋 Estado del Lote de Datos")
    if uploaded_file is not None:
        st.success(f"Archivo cargado correctamente: **{uploaded_file.name}**")
        try:
            if uploaded_file.name.endswith('.csv'):
                df_preview = pd.read_csv(uploaded_file)
                st.dataframe(df_preview.head(5), use_container_width=True)
            elif uploaded_file.name.endswith('.xlsx'):
                df_preview = pd.read_excel(uploaded_file)
                st.dataframe(df_preview.head(5), use_container_width=True)
            else:
                st.info("Archivo espacial detectado. Preparado para procesamiento por lotes.")
        except Exception as e:
            st.error(f"Error al leer la estructura previa del archivo: {e}")
    else:
        st.warning("⚠️ Por favor, seleccione un archivo en la barra lateral para comenzar.")

with col2:
    st.subheader("⏱️ Métricas de Ejecución")
    timer_placeholder = st.empty()
    timer_placeholder.metric(label="Tiempo Transcurrido", value="00:00 s")

st.markdown("---")
st.subheader("🖥️ Consola de Registro y Progreso (Log)")

# Contenedores para la barra y la consola de logs
progress_bar = st.progress(0)
status_text = st.empty()
log_container = st.empty()

# Botón de ejecución principal
if st.button("🚀 Ejecutar Proceso Automatizado"):
    if uploaded_file is None:
        st.error("Debe seleccionar un archivo de entrada antes de ejecutar el proceso.")
    else:
        logs = []
        start_time = time.time()
        
        def update_log(message):
            timestamp = datetime.now().strftime("%H:%M:%S")
            logs.append(f"[{timestamp}] {message}")
            log_container.markdown(f"<div class='log-box'>{'<br>'.join(logs)}</div>", unsafe_allow_html=True)

        update_log("Iniciando inicialización del entorno Syntro...")
        progress_bar.progress(10)
        time.sleep(0.4)
        
        update_log(f"Cargando archivo fuente: {uploaded_file.name}")
        progress_bar.progress(30)
        time.sleep(0.5)
        
        update_log(f"Aplicando algoritmo para el modo: {process_mode}")
        progress_bar.progress(60)
        time.sleep(0.7)
        
        update_log("Calculando matrices espaciales y métricas asociadas...")
        progress_bar.progress(85)
        time.sleep(0.5)
        
        elapsed_time = time.time() - start_time
        progress_bar.progress(100)
        status_text.success(f"¡Proceso completado con éxito en {elapsed_time:.2f} segundos!")
        update_log(f"Proceso finalizado exitosamente. Archivo guardado como: {output_filename}")
        
        timer_placeholder.metric(label="Tiempo Total", value=f"{elapsed_time:.2f} s")
        
        # Simulación de descarga del resultado
        if uploaded_file.name.endswith(('.csv', '.xlsx')):
            result_data = "id,parametro_1,parametro_2,estado\n1,12.5,45.1,Validado\n2,14.8,42.3,Validado"
            st.download_button(
                label="📥 Descargar Archivo de Salida Procesado",
                data=result_data,
                file_name=output_filename,
                mime="text/csv"
            )
