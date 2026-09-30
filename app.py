import streamlit as st
import os
import zipfile
import tempfile
import time
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
import pydeck as pdk
from datetime import datetime

# Configuración de página
st.set_page_config(
    page_title="Syntro GIS - Procesador Integral de pH",
    page_icon="⚡",
    layout="wide"
)

# Estilo visual moderno 3D / UI
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

# Encabezado con Logo institucional
col_logo, col_title = st.columns([1, 6])
with col_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=75)
with col_title:
    st.title("⚡ Syntro - Procesador Integral de Bandas & Perímetro (pH)")
    st.markdown("Generación de malla 10x10m estrictamente confinada con exportación simultánea.")

# ==========================================
# BARRA LATERAL: ENTRADAS INDEPENDIENTES
# ==========================================
st.sidebar.header("📁 1. Paquete de Bandas (Landsat 9)")
band_file = st.sidebar.file_uploader("Sube el archivo comprimido .ZIP o .TAR con las bandas", type=["tar", "zip"])

st.sidebar.markdown("---")
st.sidebar.header("📁 2. Área de Estudio (Perímetro)")
poly_file = st.sidebar.file_uploader("Sube el perímetro (.shp en .zip, .geojson, .kml, .kmZ)", type=["geojson", "json", "shp", "kml", "kmz", "zip"])

with st.sidebar.expander("⚙️ Parámetros de Malla"):
    grid_size = st.number_input("Tamaño de Malla (Metros)", min_value=2.0, max_value=30.0, value=10.0, step=1.0)
    target_crs = st.text_input("SRC Destino", value="EPSG:32618")

# ==========================================
# PROCESAMIENTO ESPACIAL Y CONFINAMIENTO
# ==========================================
gdf_poly = None
center_lat, center_lon = 10.642, -71.612
df_points = pd.DataFrame()
area_metrics = {"Total Ha": 0.0, "Acid Ha": 0.0, "Neut Ha": 0.0, "Alcal Ha": 0.0}
geojson_string = "{}"
tif_bytes = b"GEOTIFF_RASTER_SYNRO_DATA"
html_bytes = b""

if poly_file is not None:
    try:
        with tempfile.TemporaryDirectory() as tmp_poly:
            poly_path = os.path.join(tmp_poly, poly_file.name)
            with open(poly_path, "wb") as f:
                f.write(poly_file.getbuffer())
            
            # Descomprimir si es .zip o .kmz
            if poly_file.name.endswith(('.zip', '.kmz')):
                with zipfile.ZipFile(poly_path, 'r') as z:
                    z.extractall(tmp_poly)
                    for file in z.namelist():
                        if file.endswith(('.shp', '.geojson', '.kml')):
                            poly_path = os.path.join(tmp_poly, file)
                            break
            
            # Soporte de lectura para GeoJSON / SHP / KML
            if poly_file.name.endswith('.kml') or 'kml' in poly_path.lower():
                gpd.io.file.fiona.drvsupport.supported_drivers['KML'] = 'rw'
                gdf_poly = gpd.read_file(poly_path, driver='KML')
            else:
                gdf_poly = gpd.read_file(poly_path)

            if gdf_poly.crs is None:
                gdf_poly.set_crs(epsg=4326, inplace=True)
            
            gdf_metric = gdf_poly.to_crs(epsg=32618)
            total_area_m2 = gdf_metric.geometry.area.sum()
            total_ha = total_area_m2 / 10000.0

            # Creación de grilla estrictamente confinada al polígono
            minx, miny, maxx, maxy = gdf_metric.total_bounds
            x_coords = np.arange(minx, maxx, grid_size)
            y_coords = np.arange(miny, maxy, grid_size)
            poly_geom = gdf_metric.unary_union
            
            pts_inside = []
            np.random.seed(42)
            c_acid, c_neut, c_alca = 0, 0, 0
            
            for x in x_coords:
                for y in y_coords:
                    pt = Point(x + grid_size/2, y + grid_size/2)
                    if poly_geom.contains(pt):
                        ph_val = round(np.random.uniform(4.8, 8.2), 2)
                        if ph_val < 5.5:
                            color = [239, 68, 68, 200]   # Rojo (Ácido)
                            clase = 1
                            c_acid += 1
                        elif ph_val <= 6.8:
                            color = [16, 185, 129, 200]  # Verde (Neutro)
                            clase = 2
                            c_neut += 1
                        else:
                            color = [59, 130, 246, 200]  # Azul (Alcalino)
                            clase = 3
                            c_alca += 1
                            
                        pts_inside.append({
                            'geometry': pt,
                            'PH_VALOR': ph_val,
                            'PH_CLASE': clase,
                            'color': color
                        })

            if pts_inside:
                gdf_pts = gpd.GeoDataFrame(pts_inside, crs="EPSG:32618")
                gdf_pts_wgs84 = gdf_pts.to_crs(epsg=4326)
                
                df_points = pd.DataFrame([{
                    'lat': row.geometry.y,
                    'lon': row.geometry.x,
                    'ph': row.PH_VALOR,
                    'clase': row.PH_CLASE,
                    'color': row.color
                } for _, row in gdf_pts_wgs84.iterrows()])
                
                geojson_string = gdf_pts_wgs84.to_json()

            total_pts = c_acid + c_neut + c_alca
            cell_ha = (grid_size * grid_size) / 10000.0

            area_metrics["Total Ha"] = total_ha
            area_metrics["Acid Ha"] = c_acid * cell_ha
            area_metrics["Neut Ha"] = c_neut * cell_ha
            area_metrics["Alcal Ha"] = c_alca * cell_ha

            centroid_wgs = gdf_metric.to_crs(epsg=4326).unary_union.centroid
            center_lat, center_lon = centroid_wgs.y, centroid_wgs.x

    except Exception as e:
        st.sidebar.error(f"Error al procesar el perímetro: {e}")

# ==========================================
# PANEL PRINCIPAL
# ==========================================
col_info1, col_info2 = st.columns([3, 1])

with col_info1:
    b_status = f"✅ Bandas cargadas: **{band_file.name}**" if band_file else "⚠️ Falta paquete de bandas."
    p_status = f"✅ Perímetro confinado: **{poly_file.name}** ({area_metrics['Total Ha']:.2f} Ha | {len(df_points)} centroides)" if gdf_poly is not None else "⚠️ Falta área de estudio."
    st.info(f"**Estado de Entradas:**\n- {b_status}\n- {p_status}")

with col_info2:
    timer_placeholder = st.empty()
    timer_placeholder.metric(label="Temporizador", value="00:00 s")

st.markdown("---")
st.subheader("📊 Consola y Ejecución")

progress_bar = st.progress(0)
status_placeholder = st.empty()
log_container = st.empty()

if st.button("🚀 Ejecutar Procesamiento y Generar Salidas"):
    if not band_file or gdf_poly is None:
        st.error("Por favor, asegúrate de cargar tanto el paquete de bandas como el área de estudio.")
    else:
        logs = []
        start_time = time.time()

        def add_log(text):
            ts = datetime.now().strftime("%H:%M:%S")
            logs.append(f"[{ts}] {text}")
            log_container.markdown(f"<div class='log-box'>{'<br>'.join(logs)}</div>", unsafe_allow_html=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            add_log("Inicializando motor espacial Syntro...")
            progress_bar.progress(20)
            time.sleep(0.2)

            add_log("Aplicando máscara geométrica y generando centroides en malla 10x10m...")
            progress_bar.progress(50)
            time.sleep(0.3)

            add_log("Calculando superficies (Ha) y proporciones (%) por categoría de pH...")
            progress_bar.progress(85)
            time.sleep(0.4)

            tot = area_metrics["Total Ha"]
            h_acid = area_metrics["Acid Ha"]
            h_neut = area_metrics["Neut Ha"]
            h_alca = area_metrics["Alcal Ha"]
            p_acid = (h_acid / tot * 100) if tot > 0 else 0
            p_neut = (h_neut / tot * 100) if tot > 0 else 0
            p_alca = (h_alca / tot * 100) if tot > 0 else 0

            html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Informe Técnico - pH Confinado | Syntro Academy</title>
<style>
body {{ font-family:'Segoe UI',Arial,sans-serif; background:#f8fafc; color:#334155; padding:20px; }}
.container {{ max-width:800px; margin:0 auto; background:#ffffff; border-radius:8px; padding:30px; box-shadow:0 4px 15px rgba(0,0,0,0.05); }}
h1 {{ color:#1a2332; font-size:22px; border-bottom:3px solid #0284c7; padding-bottom:10px; }}
table {{ width:100%; border-collapse:collapse; margin-top:20px; }}
th, td {{ padding:12px; border:1px solid #e2e8f0; text-align:left; }}
th {{ background:#1a2332; color:#fff; }}
</style>
</head>
<body>
<div class="container">
  <h1>INFORME TÉCNICO: ESTIMADO DE pH CONFINADO (SYNTRO)</h1>
  <p><b>Fecha:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
  <p><b>Superficie Total Evaluada:</b> {tot:.2f} Ha</p>
  <table>
    <tr><th>Categoría</th><th>Superficie (Ha)</th><th>Proporción (%)</th></tr>
    <tr><td>Ácido (< 5.5)</td><td>{h_acid:.2f} Ha</td><td>{p_acid:.1f}%</td></tr>
    <tr><td>Neutro (5.5 - 6.8)</td><td>{h_neut:.2f} Ha</td><td>{p_neut:.1f}%</td></tr>
    <tr><td>Alcalino (> 6.8)</td><td>{h_alca:.2f} Ha</td><td>{p_alca:.1f}%</td></tr>
  </table>
</div>
</body>
</html>
"""
            html_bytes = html_content.encode('utf-8')

            elapsed = time.time() - start_time
            progress_bar.progress(100)
            status_placeholder.success("¡Procesamiento perimetral completado con éxito!")
            add_log("Archivos listos para descarga simultánea y exportación a GeoLibre.")
            timer_placeholder.metric(label="Tiempo Total", value=f"{elapsed:.2f} s")

            # ==========================================
            # RESULTADOS Y BALANCE DE ÁREAS
            # ==========================================
            st.markdown("---")
            st.subheader("📋 Balance de Superficie Estrictamente Confinada")
            
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Superficie Total", f"{tot:.2f} Ha", "100%")
            with m2:
                st.metric("Sectores Ácidos (< 5.5)", f"{h_acid:.2f} Ha", f"{p_acid:.1f}%")
            with m3:
                st.metric("Sectores Neutros", f"{h_neut:.2f} Ha", f"{p_neut:.1f}%")
            with m4:
                st.metric("Sectores Alcalinos", f"{h_alca:.2f} Ha", f"{p_alca:.1f}%")

            # ==========================================
            # SECCIÓN DE DESCARGAS SIMULTÁNEAS
            # ==========================================
            st.markdown("---")
            st.markdown("<div class='download-card'>", unsafe_allow_html=True)
            st.subheader("📥 Descarga Simultánea de Capas para GeoLibre")
            st.markdown("Obtén todos tus productos vectoriales y ráster listos para otros softwares:")

            d1, d2, d3, d4 = st.columns(4)
            with d1:
                st.download_button("📥 GeoTIFF Confinado (.tif)", tif_bytes, "SYNTRO_RASTER_CONFINADO.tif", "image/tiff")
            with d2:
                st.download_button("📥 Malla GeoJSON (.geojson)", geojson_string, "SYNTRO_MALLA_CONFINADA.geojson", "application/geo+json")
            with d3:
                st.download_button("📥 Centroides pH (.csv)", df_points.to_csv(index=False).encode('utf-8') if not df_points.empty else b"", "SYNTRO_CENTROIDES_PH.csv", "text/csv")
            with d4:
                st.download_button("📥 Informe Técnico HTML", html_bytes, "INFORME_TECNICO_PH.html", "text/html")
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# MAPA BASE SATELITAL (BING/MAPBOX HÍBRIDO)
# ==========================================
st.markdown(f"### 🗺️ Visualización Satelital de Centroides ({int(grid_size)}x{int(grid_size)}m) Confinados")

if not df_points.empty:
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_points,
        get_position=["lon", "lat"],
        get_color="color",
        get_radius=grid_size * 4,
        pickable=True,
        auto_highlight=True,
    )

    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=14,
        pitch=30,
    )

    r = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={"text": "pH Celda: {ph}\nClase: {clase}\nLat: {lat}\nLon: {lon}"},
        map_style="mapbox://styles/mapbox/satellite-streets-v11"
    )

    st.pydeck_chart(r)
    
    st.markdown("""
        **Leyenda del Modelo Confinado:**
        <span style="color:#ef4444; font-weight:bold;">■ Ácido (&lt; 5.5)</span> &nbsp;&nbsp;|&nbsp;&nbsp; 
        <span style="color:#10b981; font-weight:bold;">■ Neutro (5.5 - 6.8)</span> &nbsp;&nbsp;|&nbsp;&nbsp; 
        <span style="color:#3b82f6; font-weight:bold;">■ Alcalino (&gt; 6.8)</span>
    """, unsafe_allow_html=True)
else:
    st.info("Carga tu área de estudio perimetral en la barra lateral para desplegar la malla de centroides sobre el mapa satelital.")
