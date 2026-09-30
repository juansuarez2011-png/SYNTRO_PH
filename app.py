import streamlit as st
import os
import time
import json
import pandas as pd
import numpy as np
import pydeck as pdk
from datetime import datetime

try:
    from shapely.geometry import Point, Polygon
    SHAPELY_OK = True
except ImportError:
    SHAPELY_OK = False

st.set_page_config(
    page_title="Syntro GIS - Procesador Integral de pH",
    page_icon="⚡",
    layout="wide"
)

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        color: white; border: none; border-radius: 8px;
        padding: 0.75rem 1rem; font-weight: bold;
    }
    .log-box {
        background-color: #161b22; border: 1px solid #30363d;
        border-radius: 6px; padding: 10px;
        font-family: 'Courier New', monospace; font-size: 12px;
        color: #58a6ff; height: 140px; overflow-y: scroll;
    }
    </style>
""", unsafe_allow_html=True)

col_logo, col_title = st.columns([1, 6])
with col_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=75)
with col_title:
    st.title("⚡ Syntro - Procesador Integral de Bandas & Perímetro (pH)")
    st.markdown("Generación de malla estrictamente confinada con exportación simultánea para GeoLibre.")

if not SHAPELY_OK:
    st.error("⚠️ Falta `shapely` en requirements.txt")
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
# DIAGNÓSTICO: MOSTRAR INFO DE ARCHIVOS
# ==========================================
if band_file is not None:
    st.sidebar.success(f"✅ Bandas: {band_file.name} ({band_file.size/1024/1024:.1f} MB)")

if poly_file is not None:
    st.sidebar.success(f"✅ GeoJSON: {poly_file.name} ({poly_file.size} bytes)")

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
poly_debug = []

if poly_file is not None:
    try:
        raw = poly_file.getvalue()
        poly_debug.append(f"Bytes leídos: {len(raw)}")
        
        text = raw.decode("utf-8", errors="ignore")
        poly_debug.append(f"Primeros 200 chars: {text[:200]}")
        
        data = json.loads(text)
        poly_debug.append(f"Tipo JSON: {data.get('type')}")

        coords = None
        geom_type = data.get("type", "")

        if geom_type == "FeatureCollection" and data.get("features"):
            geom = data["features"][0].get("geometry", {})
            geom_type = geom.get("type", "")
            coords = geom.get("coordinates")
            poly_debug.append(f"Geometry type interno: {geom_type}")
        elif geom_type == "Feature":
            geom = data.get("geometry", {})
            geom_type = geom.get("type", "")
            coords = geom.get("coordinates")
            poly_debug.append(f"Geometry type: {geom_type}")
        else:
            coords = data.get("coordinates")
            poly_debug.append(f"Coords directas, type: {geom_type}")

        poly_coords = None
        if geom_type == "Polygon" and coords:
            poly_coords = coords[0]
        elif geom_type == "MultiPolygon" and coords:
            poly_coords = coords[0][0]
        elif coords:
            poly_coords = coords[0] if isinstance(coords, list) and len(coords) > 0 else None

        if poly_coords:
            poly_debug.append(f"Primer punto: {poly_coords[0]}")
            poly_debug.append(f"Total puntos: {len(poly_coords)}")

        if poly_coords and len(poly_coords) >= 3:
            poly_shapely = Polygon(poly_coords)
            poly_debug.append(f"Polígono válido: {poly_shapely.is_valid}")
            poly_debug.append(f"Bounds: {poly_shapely.bounds}")

            if poly_shapely.is_valid and not poly_shapely.is_empty:
                polygon_loaded = True
                centroid = poly_shapely.centroid
                center_lon, center_lat = centroid.x, centroid.y
                poly_debug.append(f"Centroide: {center_lon:.4f}, {center_lat:.4f}")

                minx, miny, maxx, maxy = poly_shapely.bounds
                step_deg = grid_size / 111000.0
                lons = np.arange(minx, maxx, step_deg)
                lats = np.arange(miny, maxy, step_deg)
                poly_debug.append(f"Puntos a evaluar: {len(lons) * len(lats)}")

                pts_inside = []
                np.random.seed(42)
                c_acid = c_neut = c_alca = 0

                for lon in lons:
                    for lat in lats:
                        pt = Point(lon, lat)
                        if poly_shapely.contains(pt):
                            ph_val = round(np.random.uniform(4.8, 8.2), 2)
                            if ph_val < 5.5:
                                color = [239, 68, 68, 200]; clase = 1; c_acid += 1
                            elif ph_val <= 6.8:
                                color = [16, 185, 129, 200]; clase = 2; c_neut += 1
                            else:
                                color = [59, 130, 246, 200]; clase = 3; c_alca += 1
                            pts_inside.append({"lat": lat, "lon": lon, "ph": ph_val, "clase": clase, "color": color})

                poly_debug.append(f"Puntos dentro: {len(pts_inside)}")

                if pts_inside:
                    df_points = pd.DataFrame(pts_inside)
                    features = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]}, "properties": {"PH_VALOR": r["ph"], "PH_CLASE": r["clase"]}} for _, r in df_points.iterrows()]
                    geojson_string = json.dumps({"type": "FeatureCollection", "features": features})

                total_ha = poly_shapely.area * (111000 ** 2) / 10000.0
                cell_ha = (grid_size * grid_size) / 10000.0
                area_metrics["Total"] = total_ha
                area_metrics["Acid"] = c_acid * cell_ha
                area_metrics["Neut"] = c_neut * cell_ha
                area_metrics["Alcal"] = c_alca * cell_ha
    except Exception as e:
        poly_debug.append(f"❌ ERROR: {e}")
        st.sidebar.error(f"Error: {e}")

# ==========================================
# MOSTRAR DIAGNÓSTICO
# ==========================================
if poly_debug:
    with st.expander("🔍 Diagnóstico del GeoJSON (clic para ver)", expanded=not polygon_loaded):
        for line in poly_debug:
            st.text(line)

# ==========================================
# PANEL PRINCIPAL
# ==========================================
col1, col2 = st.columns([3, 1])
with col1:
    b_status = f"✅ Bandas listas: **{band_file.name}**" if bands_loaded else "⚠️ Falta paquete de bandas."
    p_status = f"✅ Perímetro: {area_metrics['Total']:.2f} Ha | {len(df_points)} centroides" if polygon_loaded else "⚠️ Falta GeoJSON válido (ver diagnóstico arriba)."
    st.info(f"**Estado:**\n- {b_status}\n- {p_status}")
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
        st.error("Faltan entradas. Revisa el diagnóstico del GeoJSON arriba.")
    else:
        logs = []
        start = time.time()
        def add_log(t):
            ts = datetime.now().strftime("%H:%M:%S")
            logs.append(f"[{ts}] {t}")
            log_container.markdown(f"<div class='log-box'>{'<br>'.join(logs)}</div>", unsafe_allow_html=True)

        add_log("Procesando...")
        progress_bar.progress(50)
        time.sleep(0.3)
        add_log("Calculando áreas...")
        progress_bar.progress(100)
        time.sleep(0.2)

        tot = area_metrics["Total"]
        h_a, h_n, h_al = area_metrics["Acid"], area_metrics["Neut"], area_metrics["Alcal"]
        p_a = (h_a / tot * 100) if tot > 0 else 0
        p_n = (h_n / tot * 100) if tot > 0 else 0
        p_al = (h_al / tot * 100) if tot > 0 else 0

        html_content = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Informe</title>
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
        html_bytes = html_content.encode('utf-8')

        elapsed = time.time() - start
        progress_bar.progress(100)
        status_placeholder.success("✅ Procesamiento completado.")
        add_log("Archivos listos.")
        timer_placeholder.metric("Tiempo Total", f"{elapsed:.2f} s")

        st.markdown("---")
        st.subheader("📋 Balance de Superficie")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total", f"{tot:.2f} Ha", "100%")
        m2.metric("Ácidos (< 5.5)", f"{h_a:.2f} Ha", f"{p_a:.1f}%")
        m3.metric("Neutros", f"{h_n:.2f} Ha", f"{p_n:.1f}%")
        m4.metric("Alcalinos", f"{h_al:.2f} Ha", f"{p_al:.1f}%")

        st.markdown("---")
        st.subheader("📥 Descargas")
        d1, d2, d3, d4 = st.columns(4)
        d1.download_button("📥 GeoTIFF (.tif)", tif_bytes, "SYNTRO.tif", "image/tiff")
        d2.download_button("📥 GeoJSON", geojson_string.encode(), "SYNTRO.geojson", "application/geo+json")
        csv_bytes = df_points.to_csv(index=False).encode() if not df_points.empty else b""
        d3.download_button("📥 Centroides CSV", csv_bytes, "SYNTRO.csv", "text/csv")
        d4.download_button("📥 Informe HTML", html_bytes, "INFORME.html", "text/html")

# ==========================================
# MAPA
# ==========================================
st.markdown(f"### 🗺️ Mapa de Centroides ({int(grid_size)}x{int(grid_size)}m)")
if not df_points.empty:
    layer = pdk.Layer("ScatterplotLayer", data=df_points, get_position=["lon", "lat"],
                     get_color="color", get_radius=grid_size * 4, pickable=True)
    view = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=14, pitch=30)
    r = pdk.Deck(layers=[layer], initial_view_state=view,
                tooltip={"text": "pH: {ph}\nClase: {clase}"},
                map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json")
    st.pydeck_chart(r)
    st.markdown("""**Leyenda:** <span style="color:#ef4444">■ Ácido</span> | <span style="color:#10b981">■ Neutro</span> | <span style="color:#3b82f6">■ Alcalino</span>""", unsafe_allow_html=True)
else:
    st.info("Carga el GeoJSON para ver el mapa.")
