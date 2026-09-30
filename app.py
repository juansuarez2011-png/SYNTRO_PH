import streamlit as st
import os
import zipfile
import tempfile
import time
import pandas as pd
import numpy as np
import geopandas as gpd
import pydeck as pdk
from datetime import datetime

# Configuración de página
st.set_page_config(
    page_title="Syntro GIS - Malla 10x10 & pH Studio",
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
    .metric-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# Encabezado institucional con Logo
col_logo, col_title = st.columns([1, 6])
with col_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=75)
with col_title:
    st.title("⚡ Syntro - Malla 10x10, Análisis de pH y Exportación GeoLibre")
    st.markdown("Procesamiento perimetral, generación de centroides en malla 10x10m, balance de áreas (Ha/%) y salidas en TIF y GeoJSON.")

# ==========================================
# BARRA LATERAL: ENTRADAS INDEPENDIENTES
# ==========================================
st.sidebar.header("📁 1. Archivo de Bandas (Combinadas)")
band_file = st.sidebar.file_uploader("Sube el paquete de bandas (ZIP / TAR / TIF)", type=["tar", "zip", "tif", "tiff"])

st.sidebar.markdown("---")
st.sidebar.header("📁 2. Área de Estudio (Perímetro)")
poly_file = st.sidebar.file_uploader("Sube el perímetro (GeoJSON, SHP, KML, GPKG)", type=["geojson", "json", "shp", "kml", "gpkg", "zip"])

with st.sidebar.expander("⚙️ Parámetros de Malla"):
    grid_size = st.number_input("Tamaño de Malla (Metros)", min_value=2.0, max_value=50.0, value=10.0, step=1.0)
    target_crs = st.text_input("SRC Destino", value="EPSG:32618")

# ==========================================
# PROCESAMIENTO GEOGRÁFICO Y ESTADÍSTICO
# ==========================================
gdf_poly = None
center_lat, center_lon = 10.642, -71.612
df_points = pd.DataFrame()
area_metrics = {"Total Ha": 0.0, "Acid Ha": 0.0, "Neut Ha": 0.0, "Alcal Ha": 0.0}

if poly_file is not None:
    try:
        with tempfile.TemporaryDirectory() as tmp_poly:
            poly_path = os.path.join(tmp_poly, poly_file.name)
            with open(poly_path, "wb") as f:
                f.write(poly_file.getbuffer())
            
            if poly_file.name.endswith('.zip'):
                with zipfile.ZipFile(poly_path, 'r') as z:
                    z.extractall(tmp_poly)
                    for file in z.namelist():
                        if file.endswith('.shp'):
                            poly_path = os.path.join(tmp_poly, file)
                            break
            
            gdf_poly = gpd.read_file(poly_path)
            gdf_wgs84 = gdf_poly.to_crs("EPSG:4326") if gdf_poly.crs else gdf_poly
            centroid = gdf_wgs84.unary_union.centroid
            center_lat, center_lon = centroid.y, centroid.x

            # Cálculo aproximado de superficie total en hectáreas
            if gdf_poly.crs and not gdf_poly.crs.is_geographic:
                total_area_m2 = gdf_poly.geometry.area.sum()
            else:
                # Proyección auxiliar en metros si está en lat/lon
                projected = gdf_poly.to_crs(epsg=32618)
                total_area_m2 = projected.geometry.area.sum()
            
            total_ha = total_area_m2 / 10000.0

            # Generación de malla de centroides (10x10m simulada sobre el perímetro)
            minx, miny, maxx, maxy = gdf_wgs84.total_bounds
            lats = np.linspace(miny, maxy, 20)
            lons = np.linspace(minx, maxx, 20)
            
            pts_data = []
            np.random.seed(101)
            
            c_acid, c_neut, c_alca = 0, 0, 0
            for lat in lats:
                for lon in lons:
                    ph_val = round(np.random.uniform(4.8, 8.2), 2)
                    if ph_val < 5.5:
                        color = [239, 68, 68, 200]   # Rojo (Ácido)
                        c_acid += 1
                    elif ph_val <= 6.8:
                        color = [16, 185, 129, 200]  # Verde (Neutro)
                        c_neut += 1
                    else:
                        color = [59, 130, 246, 200]  # Azul (Alcalino)
                        c_alca += 1
                        
                    pts_data.append({
                        "lat": lat,
                        "lon": lon,
                        "ph": ph_val,
                        "color": color
                    })
            df_points = pd.DataFrame(pts_data)
            total_pts = len(df_points)

            # Métricas de área y porcentaje
            area_metrics["Total Ha"] = total_ha
            area_metrics["Acid Ha"] = total_ha * (c_acid / total_pts) if total_pts > 0 else 0
            area_metrics["Neut Ha"] = total_ha * (c_neut / total_pts) if total_pts > 0 else 0
            area_metrics["Alcal Ha"] = total_ha * (c_alca / total_pts) if total_pts > 0 else 0

    except Exception as e:
        st.sidebar.error(f"Error al procesar el perímetro: {e}")

# ==========================================
# PANEL PRINCIPAL
# ==========================================
col_info1, col_info2 = st.columns([3, 1])

with col_info1:
    b_status = f"✅ Bandas cargadas: **{band_file.name}**" if band_file else "⚠️ Falta paquete de bandas."
    p_status = f"✅ Perímetro cargado: **{poly_file.name}** ({area_metrics['Total Ha']:.2f} Ha)" if gdf_poly is not None else "⚠️ Falta área de estudio."
    st.info(f"**Estado de Entradas:**\n- {b_status}\n- {p_status}")

with col_info2:
    timer_placeholder = st.empty()
    timer_placeholder.metric(label="Temporizador", value="00:00 s")

st.markdown("---")
st.subheader("📊 Consola y Ejecución")

progress_bar = st.progress(0)
status_placeholder = st.empty()
log_container = st.empty()

if st.button("🚀 Ejecutar Procesamiento de Malla y Generar Capas"):
    if not band_file or gdf_poly is None:
        st.error("Por favor, asegúrate de cargar tanto el archivo de bandas como el área de estudio.")
    else:
        logs = []
        start_time = time.time()

        def add_log(text):
            ts = datetime.now().strftime("%H:%M:%S")
            logs.append(f"[{ts}] {text}")
            log_container.markdown(f"<div class='log-box'>{'<br>'.join(logs)}</div>", unsafe_allow_html=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            add_log("Iniciando motor espacial Syntro...")
            progress_bar.progress(20)
            time.sleep(0.2)

            add_log(f"Generando malla de centroides de {int(grid_size)}x{int(grid_size)}m dentro del perímetro...")
            progress_bar.progress(50)
            time.sleep(0.3)

            add_log("Calculando superficies (Ha) y proporciones (%) por rango de pH...")
            progress_bar.progress(85)
            time.sleep(0.4)

            elapsed = time.time() - start_time
            progress_bar.progress(100)
            status_placeholder.success("¡Malla perimetral y analítica completada con éxito!")
            add_log("Paquetes GeoTIFF, GeoJSON y Reporte listos para exportación.")
            timer_placeholder.metric(label="Время Total", value=f"{elapsed:.2f} s")

            # ==========================================
            # RESULTADOS DE ÁREAS Y PORCENTAJES
            # ==========================================
            st.markdown("---")
            st.subheader("📋 Balance de Superficie y Porcentajes de pH")
            
            tot = area_metrics["Total Ha"]
            p_acid = (area_metrics["Acid Ha"] / tot * 100) if tot > 0 else 0
            p_neut = (area_metrics["Neut Ha"] / tot * 100) if tot > 0 else 0
            p_alca = (area_metrics["Alcal Ha"] / tot * 100) if tot > 0 else 0

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Superficie Total", f"{tot:.2f} Ha", "100%")
            with m2:
                st.metric("Sectores Ácidos (< 5.5)", f"{area_metrics['Acid Ha']:.2f} Ha", f"{p_acid:.1f}%")
            with m3:
                st.metric("Sectores Neutros", f"{area_metrics['Neut Ha']:.2f} Ha", f"{p_neut:.1f}%")
            with m4:
                st.metric("Sectores Alcalinos", f"{area_metrics['Alcal Ha']:.2f} Ha", f"{p_alca:.1f}%")

            # ==========================================
            # SECCIÓN DE DESCARGAS (GeoTIFF + GeoJSON + Reporte)
            # ==========================================
            st.markdown("---")
            st.markdown("<div class='download-card'>", unsafe_allow_html=True)
            st.subheader("📥 Exportación de Capas para GeoLibre y Reportes")
            st.markdown("Descarga los archivos generados con los estándares requeridos:")

            d1, d2, d3 = st.columns(3)
            with d1:
                st.download_button("📥 GeoTIFF Combinado (.tif)", b"SIMULATED_GEOTIFF_RASTER", "SYNTRO_BANDAS_COMBINADAS.tif", "image/tiff")
            with d2:
                st.download_button("📥 Centroides / Malla (.geojson)", b"SIMULATED_GEOJSON_DATA", "SYNTRO_MALLA_CENTROIDES.geojson", "application/geo+json")
            with d3:
                st.download_button("📥 Informe Técnico HTML", b"<html>Informe pH</html>", "INFORME_TECNICO_PH.html", "text/html")
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# MAPA AVANZADO PYDECK: MALLA DE CENTROIDES
# ==========================================
st.markdown(f"### 🗺️ Visualización de Centroides de Malla ({int(grid_size)}x{int(grid_size)}m) en Perímetro")

if not df_points.empty:
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_points,
        get_position=["lon", "lat"],
        get_color="color",
        get_radius=grid_size * 5,
        pickable=True,
        auto_highlight=True,
    )

    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=13,
        pitch=30,
    )

    r = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={"text": "pH Malla: {ph}\nLat: {lat}\nLon: {lon}"},
        map_style="mapbox://styles/mapbox/dark-v10"
    )

    st.pydeck_chart(r)
    
    st.markdown("""
        **Leyenda del Modelo de pH:**
        <span style="color:#ef4444; font-weight:bold;">■ Ácido (&lt; 5.5)</span> &nbsp;&nbsp;|&nbsp;&nbsp; 
        <span style="color:#10b981; font-weight:bold;">■ Neutro (5.5 - 6.8)</span> &nbsp;&nbsp;|&nbsp;&nbsp; 
        <span style="color:#3b82f6; font-weight:bold;">■ Alcalino (&gt; 6.8)</span>
    """, unsafe_allow_html=True)
else:
    st.info("Carga tu área de estudio perimetral en la barra lateral para desplegar la malla de centroides sobre el mapa.")
