import streamlit as st
import os
import tempfile
import numpy as np
import datetime
from PIL import Image
import folium
from streamlit_folium import st_folium
import simplekml
from docx import Document
from docx.shared import Inches

# Configuración de la página
st.set_page_config(
    page_title="Syntro Academy - Estimado de pH y Suelos",
    page_icon="🌱",
    layout="wide"
)

# Cabecera con Logotipo y Estilo
col_logo, col_title = st.columns([1, 4])
with col_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=130)
    else:
        st.info("Coloca 'logo.png' en la carpeta.")

with col_title:
    st.markdown("""
        <div style='background: linear-gradient(135deg, #1a2332, #0f172a); padding: 15px; border-radius: 12px; border-bottom: 4px solid #06b6d4; color: white;'>
            <h2 style='margin:0; font-size: 20px;'>Syntro Academy • Geotecnología y Suelos</h2>
            <h1 style='color: #06b6d4; font-size: 22px; margin:0;'>MODELO ESPACIAL DE pH (CRITERIO ESPECTRAL)</h1>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Panel lateral para controles
st.sidebar.header("⚙️ Parámetros de Análisis")
band_zip = st.sidebar.file_uploader("1. Bandas Landsat (ZIP con B5 y B6 en TIF)", type=["zip"])
pixel_size = st.sidebar.number_input("Tamaño de Píxel (Metros)", min_value=2.0, max_value=30.0, value=10.0, step=1.0)

if band_zip:
    if st.sidebar.button("🚀 Ejecutar Modelo de pH"):
        with st.spinner("Procesando bandas espectrales y generando entregables..."):
            temp_dir = tempfile.mkdtemp(prefix="syntro_")
            
            try:
                import zipfile
                zip_path = os.path.join(temp_dir, band_zip.name)
                with open(zip_path, "wb") as f:
                    f.write(band_zip.read())
                
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                b5_path, b6_path = None, None
                for r, d, files in os.walk(temp_dir):
                    for n in files:
                        up = n.upper()
                        if ('B5' in up or 'NIR' in up) and up.endswith(('.TIF', '.TIFF')) and 'QA' not in up:
                            b5_path = os.path.join(r, n)
                        elif ('B6' in up or 'SWIR' in up) and up.endswith(('.TIF', '.TIFF')) and 'QA' not in up:
                            b6_path = os.path.join(r, n)
                
                if not b5_path or not b6_path:
                    st.error("No se detectaron las bandas B5 y B6 (TIF) dentro del ZIP.")
                    st.stop()

                img_b5 = Image.open(b5_path)
                img_b6 = Image.open(b6_path)
                
                arr_b5 = np.array(img_b5, dtype=np.float32)
                arr_b6 = np.array(img_b6, dtype=np.float32)

                if arr_b5.shape != arr_b6.shape:
                    arr_b6 = np.array(img_b6.resize((arr_b5.shape[1], arr_b5.shape[0])), dtype=np.float32)

                mask = (arr_b5 != 0) & (arr_b6 != 0) & np.isfinite(arr_b5) & np.isfinite(arr_b6)
                den = arr_b5 + arr_b6
                ndmi_arr = np.full(arr_b5.shape, -9999.0, dtype=np.float32)
                valid_den = mask & (den != 0)
                ndmi_arr[valid_den] = (arr_b5[valid_den] - arr_b6[valid_den]) / den[valid_den]

                valid_data = valid_den & (ndmi_arr >= -1.0) & (ndmi_arr <= 1.0)
                
                ha_px = (pixel_size * pixel_size) / 10000.0
                vals = ndmi_arr[valid_data]
                p33, p66 = np.percentile(vals, 33), np.percentile(vals, 66)

                ph_cat = np.zeros(ndmi_arr.shape, dtype=np.uint8)
                ph_cat[valid_data & (ndmi_arr <= p33)] = 1
                ph_cat[valid_data & (ndmi_arr > p33) & (ndmi_arr <= p66)] = 2
                ph_cat[valid_data & (ndmi_arr > p66)] = 3

                raster_output_path = os.path.join(temp_dir, "mapa_ph_clasificado.tif")
                color_palette = np.array([[0,0,0], [239,68,68], [34,197,94], [59,130,246]], dtype=np.uint8)
                img_out = Image.fromarray(color_palette[ph_cat], mode="RGB")
                img_out.save(raster_output_path)

                rows, cols = np.where(ph_cat > 0)
                if len(rows) > 800:
                    indices = np.random.choice(len(rows), 800, replace=False)
                    rows, cols = rows[indices], cols[indices]

                points_data = []
                base_lat, base_lon = 10.65, -71.62
                for row, col in zip(rows, cols):
                    clase = int(ph_cat[row, col])
                    lat = base_lat + (row * 0.0001)
                    lon = base_lon + (col * 0.0001)
                    nombre_clase = {1: "Ácido (< 5.5)", 2: "Neutro (5.5 - 6.8)", 3: "Alcalino (> 6.8)"}
                    points_data.append({"lat": lat, "lon": lon, "PH_CLASE": clase, "PH_NOMBRE": nombre_clase.get(clase, "N/D")})

                st.session_state['points_data'] = points_data
                st.session_state['raster_output_path'] = raster_output_path
                st.session_state['temp_dir'] = temp_dir
                st.session_state['processed'] = True

                c1, c2, c3 = int(np.sum(ph_cat == 1)), int(np.sum(ph_cat == 2)), int(np.sum(ph_cat == 3))
                total_px = max(1, c1 + c2 + c3)
                
                st.session_state['stats'] = {
                    'h_acid': c1 * ha_px, 'p_acid': (c1 / total_px) * 100,
                    'h_neut': c2 * ha_px, 'p_neut': (c2 / total_px) * 100,
                    'h_alca': c3 * ha_px, 'p_alca': (c3 / total_px) * 100,
                    'total_ha': (c1 + c2 + c3) * ha_px,
                    'fecha': datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                st.success("¡Modelo ejecutado correctamente!")

            except Exception as e:
                st.error(f"Error en el procesamiento: {e}")

    if st.session_state.get('processed', False):
        stats = st.session_state['stats']
        points_data = st.session_state['points_data']
        raster_output_path = st.session_state['raster_output_path']
        temp_out = st.session_state.get('temp_dir', tempfile.mkdtemp())

        st.markdown("### 📊 Resultados y Superficies")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Superficie Total", f"{stats['total_ha']:.2f} Ha")
        c2.metric("Ácido (< 5.5)", f"{stats['h_acid']:.2f} Ha", f"{stats['p_acid']:.1f}%")
        c3.metric("Neutro (5.5 - 6.8)", f"{stats['h_neut']:.2f} Ha", f"{stats['p_neut']:.1f}%")
        c4.metric("Alcalino (> 6.8)", f"{stats['h_alca']:.2f} Ha", f"{stats['p_alca']:.1f}%")

        st.markdown("### 🗺️ Visor Geográfico")
        mean_lat = sum(p['lat'] for p in points_data) / len(points_data)
        mean_lon = sum(p['lon'] for p in points_data) / len(points_data)
        
        m = folium.Map(location=[mean_lat, mean_lon], zoom_start=14)
        color_map = {1: "#ef4444", 2: "#22c55e", 3: "#3b82f6"}
        for p in points_data:
            folium.CircleMarker(
                location=[p['lat'], p['lon']], radius=3,
                color=color_map.get(p['PH_CLASE'], "#333"),
                fill=True, fill_color=color_map.get(p['PH_CLASE'], "#333"), fill_opacity=0.8,
                popup=f"Clase: {p['PH_NOMBRE']}"
            ).add_to(m)

        st_folium(m, width=900, height=400)

        # Generar Reportes y Descargas
        doc = Document()
        if os.path.exists("logo.png"):
            doc.add_picture("logo.png", width=Inches(1.5))
        doc.add_heading('Syntro Academy - Informe Técnico de Suelos', 0)
        doc.add_paragraph(f"Fecha: {stats['fecha']}")
        doc.add_heading('Superficies Evaluadas', level=1)
        doc.add_paragraph(f"• Total: {stats['total_ha']:.2f} Ha\n• Ácido: {stats['h_acid']:.2f} Ha\n• Neutro: {stats['h_neut']:.2f} Ha\n• Alcalino: {stats['h_alca']:.2f} Ha")
        doc_path = os.path.join(temp_out, "Informe_pH.docx")
        doc.save(doc_path)

        kml_path = os.path.join(temp_out, "puntos_ph.kml")
        kml = simplekml.Kml()
        for p in points_data:
            kml.newpoint(name=str(p['PH_NOMBRE']), coords=[(p['lon'], p['lat'])])
        kml.save(kml_path)

        d1, d2, d3 = st.columns(3)
        with d1:
            if os.path.exists(doc_path):
                with open(doc_path, "rb") as f:
                    st.download_button("📄 Informe Word", data=f.read(), file_name="Informe_pH_Syntro.docx")
        with d2:
            if os.path.exists(raster_output_path):
                with open(raster_output_path, "rb") as f:
                    st.download_button("🗺 Ráster .TIF", data=f.read(), file_name="mapa_ph.tif")
        with d3:
            if os.path.exists(kml_path):
                with open(kml_path, "rb") as f:
                    st.download_button("🌎 KML Earth", data=f.read(), file_name="puntos_syntro.kml")
else:
    st.info("👈 Sube el archivo ZIP con tus bandas (B5 y B6 en formato TIF) en el panel izquierdo para comenzar.")
