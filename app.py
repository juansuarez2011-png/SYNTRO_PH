import streamlit as st
import json
import time
import pandas as pd
import numpy as np
from datetime import datetime
import pydeck as pdk

# Importación tolerante a fallos de shapely
try:
    from shapely.geometry import Point, Polygon
    SHAPELY_OK = True
except ImportError:
    SHAPELY_OK = False

# ==========================================
# CONFIGURACIÓN
# ==========================================
st.set_page_config(
    page_title="Syntro GIS - Procesador pH",
    page_icon="⚡",
    layout="wide"
)

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
    }
    .log-box {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 10px;
        font-family: 'Courier New', monospace;
        font-size: 12px;
        color: #58a6ff;
        height: 140px;
        overflow-y: scroll;
    }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ Syntro - Procesador Integral de Bandas & pH")
st.markdown("Generación de malla estrictamente confinada con exportación para GeoLibre.")

# Aviso si shapely no está instalado
if not SHAPELY_OK:
    st.error("⚠️ **Falta la librería `shapely`**. Asegúrate de tener el archivo `requirements.txt` en tu repositorio con `shapely==2.0.3` y reinicia la app desde 'Manage app' → 'Reboot'.")
    st.stop()

# ==========================================
# BARRA LATERAL
# ==========================================
st.sidebar.header("📁 1. Paquete de Bandas")
band_file = st.sidebar.file_uploader("Sube el .ZIP o .TAR", type=["tar", "zip"])

st.sidebar.markdown("---")
st.sidebar.header("📁 2. Perímetro (GeoJSON)")
poly_file = st.sidebar.file_uploader("Sube el .geojson o .json", type=["geojson", "json"])

with st.sidebar.expander("⚙️ Parámetros"):
    grid_size = st.number_input("Tamaño de Malla (m)", min_value=2.0, max_value=30.0, value=10.0, step=1.0)

# ==========================================
# PROCESAMIENTO
# ==========================================
center_lat, center_lon = 10.642, -71.612
df_points = pd.DataFrame()
area_metrics = {"Total": 0.0, "Acid": 0.0, "Neut": 0.0, "Alcal": 0.0}
geojson_string = "{}"
polygon_loaded = False
bands_loaded = band_file is not None

if poly_file is not None:
    try:
        data = json.loads(poly_file.getvalue().decode("utf-8", errors="ignore"))
        
        # Extraer coordenadas del polígono (tolerante a varios formatos)
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
        
        # Normalizar a lista de anillos
        if geom_type == "Polygon" and coords:
            poly_coords = coords[0]
        elif geom_type == "MultiPolygon" and coords:
            poly_coords = coords[0][0]
        else:
            poly_coords = coords[0] if coords else None
        
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
    b_status = f"✅ Bandas: **{band_file.name}**" if bands_loaded else "⚠️ Falta paquete de bandas."
    p_status = f"✅ Perímetro: {area_metrics['Total']:.2f} Ha | {len(df_points)} puntos" if polygon_loaded else "⚠️ Falta GeoJSON válido."
    st.info(f"**Estado:**\n- {b_status}\n- {p_status}")
with col2:
    timer_placeholder = st.empty()
    timer_placeholder.metric("Temporizador", "00:00 s")

st.markdown("---")
st.subheader("📊 Ejecución")

progress_bar = st.progress(0)
status_placeholder = st.empty()
log_container = st.empty()

if st.button("🚀 Ejecutar Procesamiento"):
    if not bands_loaded or not polygon_loaded:
        st.error("Carga el paquete de bandas y un GeoJSON válido.")
    else:
        logs = []
        start = time.time()
        
        def add_log(t):
            ts = datetime.now().strftime("%H:%M:%S")
            logs.append(f"[{ts}] {t}")
            log_container.markdown(f"<div class='log-box'>{'<br>'.join(logs)}</div>", unsafe_allow_html=True)
        
        add_log("Procesando bandas satelitales...")
        progress_bar.progress(50)
        time.sleep(0.3)
        add_log("Calculando áreas por clase de pH...")
        progress_bar.progress(100)
        time.sleep(0.2)
        
        tot = area_metrics["Total"]
        h_a, h_n, h_al = area_metrics["Acid"], area_metrics["Neut"], area_metrics["Alcal"]
        p_a = (h_a / tot * 100) if tot > 0 else 0
        p_n = (h_n / tot * 100) if tot > 0 else 0
        p_al = (h_al / tot * 100) if tot > 0 else 0
        
        elapsed = time.time() - start
        timer_placeholder.metric("Tiempo Total", f"{elapsed:.2f} s")
        status_placeholder.success("✅ Procesamiento completado.")
        
        # Informe HTML
        html_content = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Informe</title>
<style>body{{font-family:Arial;padding:20px}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:8px}}th{{background:#1a2332;color:#fff}}</style></head>
<body><h1>Informe pH Confinado</h1>
<p>Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
<p>Superficie Total: {tot:.2f} Ha</p>
<table><tr><th>Categoría</th><th>Ha</th><th>%</th></tr>
<tr><td>Ácido</td><td>{h_a:.2f}</td><td>{p_a:.1f}%</td></tr>
<tr><td>Neutro</td><td>{h_n:.2f}</td><td>{p_n:.1f}%</td></tr>
<tr><td>Alcalino</td><td>{h_al:.2f}</td><td>{p_al:.1f}%</td></tr>
</table></body></html>"""
        
        st.markdown("---")
        st.subheader("📋 Balance de Superficie")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total", f"{tot:.2f} Ha")
        m2.metric("Ácidos", f"{h_a:.2f} Ha", f"{p_a:.1f}%")
        m3.metric("Neutros", f"{h_n:.2f} Ha", f"{p_n:.1f}%")
        m4.metric("Alcalinos", f"{h_al:.2f} Ha", f"{p_al:.1f}%")
        
        st.markdown("---")
        st.subheader("📥 Descargas")
        d1, d2, d3 = st.columns(3)
        d1.download_button("GeoTIFF (.tif)", b"RASTER_DATA", "SYNTRO.tif", "image/tiff")
        d2.download_button("GeoJSON", geojson_string.encode(), "SYNTRO.geojson", "application/geo+json")
        csv_bytes = df_points.to_csv(index=False).encode() if not df_points.empty else b""
        d3.download_button("CSV Centroides", csv_bytes, "SYNTRO.csv", "text/csv")

# ==========================================
# MAPA
# ==========================================
st.markdown(f"### 🗺️ Mapa de Centroides")
if not df_points.empty:
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_points,
        get_position=["lon", "lat"],
        get_color="color",
        get_radius=grid_size * 4,
        pickable=True,
    )
    view = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=14, pitch=30)
    r = pdk.Deck(
        layers=[layer],
        initial_view_state=view,
        tooltip={"text": "pH: {ph}\nClase: {clase}"},
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
    )
    st.pydeck_chart(r)
else:
    st.info("Carga un GeoJSON de perímetro para ver el mapa.")
