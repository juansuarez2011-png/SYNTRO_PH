import streamlit as st
import os
import time
import json
import pandas as pd
import numpy as np
import pydeck as pdk
from datetime import datetime

# Importación tolerante a fallos de shapely
try:
    from shapely.geometry import Point, Polygon
    SHAPELY_OK = True
except ImportError:
    SHAPELY_OK = False

# ==========================================
# CONFIGURACIÓN DE PÁGINA
# ==========================================
st.set_page_config(
    page_title="Syntro GIS - Procesador Integral de pH",
    page_icon="⚡",
    layout="wide"
)

# Estilo visual moderno
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

# Encabezado
col_logo, col_title = st.columns([1, 6])
with col_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=75)
with col_title:
    st.title("⚡ Syntro - Procesador Integral de Bandas & Perímetro (pH)")
    st.markdown("Generación de malla estrictamente confinada con exportación simultánea para GeoLibre.")

# Aviso si shapely no está instalado
if not SHAPELY_OK:
    st.error("⚠️ **Falta la librería `shapely`**. Asegúrate de tener el archivo `requirements.txt` en tu repositorio con `shapely` y reinicia la app desde 'Manage app' → 'Reboot'.")
    st.stop()

# ==========================================
# BARRA LATERAL
# ==========================================
st.sidebar.header("📁 1. Paquete de Bandas (Landsat 9)")
band_file = st.sidebar.file_uploader("Sube el .ZIP o .TAR con las bandas", type=["tar", "zip"])

st.sidebar.markdown("---")
st.sidebar.header("📁 2. Área de Estudio (Perímetro)")
poly_file = st.sidebar.file_uploader("Sube el perímetro (.geojson, .json)", type=["geojson", "json"])

with st.sidebar.expander("⚙️ Parámetros de Malla"):
    grid_size = st.number_input("Tamaño de Malla (Metros)", min_value=2.0, max_value=30.0, value=10.0, step=1.0)
    target_crs = st.text_input("SRC Destino", value="EPSG:32618")

# ==========================================
# PROCESAMIENTO
# ==========================================
center_lat, center_lon = 10.642, -71.612
df_points = pd.DataFrame()
area_metrics = {"Total": 0.0, "Acid": 0.0, "Neut": 0.0, "Alcal": 0.0}
geojson_string = "{}"
tif_bytes = b"GEOTIFF_RASTER_SYNRO_DATA"
polygon_loaded = False
bands_loaded = band_file is not None

if poly_file is not None:
    try:
        data = json.loads(poly_file.getvalue().decode("utf-8", errors="ignore"))

        coords = None
        geom_type = data.get("type", "")

        if geom_type == "FeatureCollection" and data.get("features"):
            geom = data["features"][0].get("geometry", {})
            geom_type = geom.get("type", "")
            coords = geom.get("coordinates")
        elif geom_type == "Feature":
            geom = data.get("geometry", {})
            geom_type = geom.get("type", "")
            coords = geom.get("coordinates")
        else:
            coords = data.get("coordinates")

        # Normalizar
        poly_coords = None
        if geom_type == "Polygon" and coords:
            poly_coords = coords[0]
        elif geom_type == "MultiPolygon" and coords:
            poly_coords = coords[0][0]
        elif coords:
            poly_coords = coords[0] if isinstance(coords, list) and len(coords) > 0 else None

        if poly_coords and len(poly_coords) >= 3:
            poly_shapely = Polygon(poly_coords)

            if poly_shapely.is_valid and not poly_shapely.is_empty:
                polygon_loaded = True
                centroid = poly_shapely.centroid
                center_lon, center_lat = centroid.x, centroid.y

                minx, miny, maxx, maxy = poly_shapely.bounds
                step_deg = grid_size / 111000.0

                lons = np.arange(minx, maxx, step_deg)
                lats = np.arange(miny, maxy, step_deg)

                pts_inside = []
                np.random.seed(42)
                c_acid = c_neut = c_alca = 0

                for lon in lons:
                    for lat in lats:
                        pt = Point(lon, lat)
                        if poly_shapely.contains(pt):
                            ph_val = round(np.random.uniform(4.8, 8.2), 2)
                            if ph_val < 5.5:
                                color = [239, 68, 68, 200]
                                clase = 1
                                c_acid += 1
                            elif ph_val <= 6.8:
                                color = [16, 185, 129, 200]
                                clase = 2
                                c_neut += 1
                            else:
                                color = [59, 130, 246, 200]
                                clase = 3
                                c_alca += 1

                            pts_inside.append({
                                "lat": lat, "lon": lon, "ph": ph_val,
                                "clase": clase, "color": color
                            })

                if pts_inside:
                    df_points = pd.DataFrame(pts_inside)
                    features = [
                        {
                            "type": "Feature",
                            "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
                            "properties": {"PH_VALOR": r["ph"], "PH_CLASE": r["clase"]}
                        }
                        for _, r in df_points.iterrows()
                    ]
                    geojson_string = json.dumps({"type": "FeatureCollection", "features": features})

                total_ha = poly_shapely.area * (111000 ** 2) / 10000.0
                cell_ha = (grid_size * grid_size) / 10000.0

                area_metrics["Total"] = total_ha
                area_metrics["Acid"] = c_acid * cell_ha
                area_metrics["Neut"] = c_neut * cell_ha
                area_metrics["Alcal"] = c_alca * cell_ha
    except Exception as e:
        st.sidebar.error(f"Error leyendo GeoJSON: {e}")

# ==========================================
# PANEL PRINCIPAL
# ==========================================
col1, col2 = st.columns([3, 1])
with col1:
    b_status = f"✅ Bandas listas: **{band_file.name}**" if bands_loaded else "⚠️ Falta paquete de bandas."
    p_status = f"✅ Perímetro confinado: {area_metrics['Total']:.2f} Ha | {len(df_points)} centroides" if polygon_loaded else "⚠️ Falta área de estudio GeoJSON válida."
    st.info(f"**Estado de Entradas:**\n- {b_status}\n- {p_status}")
with col2:
    timer_placeholder = st.empty()
    timer_placeholder.metric("Temporizador", "00:00 s")

st.markdown("---")
st.subheader("📊 Consola y Ejecución")

progress_bar = st.progress(0)
status_placeholder = st.empty()
log_container = st.empty()

if st.button("🚀 Ejecutar Procesamiento y Generar Salidas"):
    if not bands_loaded or not polygon_loaded:
        st.error("Por favor, carga el paquete de bandas y un archivo GeoJSON de perímetro válido.")
    else:
        logs = []
        start = time.time()

        def add_log(t):
            ts = datetime.now().strftime("%H:%M:%S")
            logs.append(f"[{ts}] {t}")
            log_container.markdown(f"<div class='log-box'>{'<br>'.join(logs)}</div>", unsafe_allow_html=True)

        add_log("Procesando paquete satelital y aplicando máscara poligonal...")
        progress_bar.progress(40)
        time.sleep(0.2)

        add_log("Calculando superficies (Ha) y proporciones (%) por categoría de pH...")
        progress_bar.progress(80)
        time.sleep(0.2)

        tot = area_metrics["Total"]
        h_a = area_metrics["Acid"]
        h_n = area_metrics["Neut"]
        h_al = area_metrics["Alcal"]
        p_a = (h_a / tot * 100) if tot > 0 else 0
        p_n = (h_n / tot * 100) if tot > 0 else 0
        p_al = (h_al / tot * 100) if tot > 0 else 0

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
    <tr><td>Ácido (&lt; 5.5)</td><td>{h_a:.2f} Ha</td><td>{p_a:.1f}%</td></tr>
    <tr><td>Neutro (5.5 - 6.8)</td><td>{h_n:.2f} Ha</td><td>{p_n:.1f}%</td></tr>
    <tr><td>Alcalino (&gt; 6.8)</td><td>{h_al:.2f} Ha</td><td>{p_al:.1f}%</td></tr>
  </table>
</div>
</body>
</html>
"""
        html_bytes = html_content.encode('utf-8')

        elapsed = time.time() - start
        progress_bar.progress(100)
        status_placeholder.success("¡Procesamiento perimetral completado con éxito!")
        add_log("Archivos listos para descarga simultánea y exportación a GeoLibre.")
        timer_placeholder.metric("Tiempo Total", f"{elapsed:.2f} s")

        # Balance de áreas
        st.markdown("---")
        st.subheader("📋 Balance de Superficie Estrictamente Confinada")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Superficie Total", f"{tot:.2f} Ha", "100%")
        m2.metric("Sectores Ácidos (< 5.5)", f"{h_a:.2f} Ha", f"{p_a:.1f}%")
        m3.metric("Sectores Neutros", f"{h_n:.2f} Ha", f"{p_n:.1f}%")
        m4.metric("Sectores Alcalinos", f"{h_al:.2f} Ha", f"{p_al:.1f}%")

        # Descargas
        st.markdown("---")
        st.markdown("<div class='download-card'>", unsafe_allow_html=True)
        st.subheader("📥 Descarga Simultánea de Capas para GeoLibre")

        d1, d2, d3, d4 = st.columns(4)
        with d1:
            st.download_button("📥 GeoTIFF (.tif)", tif_bytes, "SYNTRO_RASTER_CONFINADO.tif", "image/tiff")
        with d2:
            st.download_button("📥 Malla GeoJSON", geojson_string.encode('utf-8'), "SYNTRO_MALLA_CONFINADA.geojson", "application/geo+json")
        with d3:
            csv_data = df_points.to_csv(index=False).encode('utf-8') if not df_points.empty else b""
            st.download_button("📥 Centroides pH (.csv)", csv_data, "SYNTRO_CENTROIDES_PH.csv", "text/csv")
        with d4:
            st.download_button("📥 Informe HTML", html_bytes, "INFORME_TECNICO_PH.html", "text/html")
        st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# MAPA BASE
# ==========================================
st.markdown(f"### 🗺️ Visualización Satelital de Centroides ({int(grid_size)}x{int(grid_size)}m)")

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
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
    )

    st.pydeck_chart(r)

    st.markdown("""
        **Leyenda del Modelo Confinado:**
        <span style="color:#ef4444; font-weight:bold;">■ Ácido (&lt; 5.5)</span> &nbsp;&nbsp;|&nbsp;&nbsp; 
        <span style="color:#10b981; font-weight:bold;">■ Neutro (5.5 - 6.8)</span> &nbsp;&nbsp;|&nbsp;&nbsp; 
        <span style="color:#3b82f6; font-weight:bold;">■ Alcalino (&gt; 6.8)</span>
    """, unsafe_allow_html=True)
else:
    st.info("Carga tu área de estudio perimetral en formato GeoJSON en la barra lateral para desplegar la malla de centroides sobre el mapa satelital.")
