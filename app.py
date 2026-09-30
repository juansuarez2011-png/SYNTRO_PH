import streamlit as st
import os
import tempfile
import numpy as np
import rasterio
import rasterio.mask
import geopandas as gpd
from shapely.geometry import Point
import folium
from streamlit_folium import st_folium
import zipfile
import simplekml
import datetime
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
        st.info("Coloca 'logo.png' en la carpeta del proyecto.")

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
poly_file = st.sidebar.file_uploader("2. Perímetro (GeoJSON o SHP en ZIP)", type=["geojson", "zip"])
pixel_size = st.sidebar.number_input("Tamaño de Píxel (Metros)", min_value=2.0, max_value=30.0, value=10.0, step=1.0)

if band_zip and poly_file:
    if st.sidebar.button("🚀 Ejecutar Modelo de pH"):
        with st.spinner("Procesando bandas espectrales, calculando clases y generando entregables..."):
            # Usar una ruta temporal persistente durante la sesión
            temp_dir = tempfile.mkdtemp(prefix="syntro_streamlit_")
            
            try:
                # 1. Extraer el ZIP de las bandas
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
                    st.error("No se detectaron las bandas B5 y B6 (TIF) dentro del archivo ZIP cargado.")
                    st.stop()

                # 2. Cargar Perímetro con Geopandas
                poly_path = os.path.join(temp_dir, poly_file.name)
                with open(poly_path, "wb") as f:
                    f.write(poly_file.read())
                
                if poly_file.name.endswith('.zip'):
                    with zipfile.ZipFile(poly_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                    shp_files = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.endswith('.shp')]
                    gdf = gpd.read_file(shp_files[0])
                else:
                    gdf = gpd.read_file(poly_path)

                target_crs = "EPSG:32618"
                if gdf.crs != target_crs:
                    gdf = gdf.to_crs(target_crs)

                # 3. Recortar y procesar con Rasterio
                with rasterio.open(b5_path) as src_b5:
                    gdf_raster_crs = gdf.to_crs(src_b5.crs)
                    geom_raster_crs = gdf_raster_crs.unary_union
                    
                    out_image_b5, out_transform_b5 = rasterio.mask.mask(
                        src_b5, [geom_raster_crs], crop=True, nodata=0
                    )
                    meta = src_b5.meta.copy()

                with rasterio.open(b6_path) as src_b6:
                    out_image_b6, _ = rasterio.mask.mask(
                        src_b6, [geom_raster_crs], crop=True, nodata=0
                    )

                arr_b5 = out_image_b5[0].astype(np.float32)
                arr_b6 = out_image_b6[0].astype(np.float32)

                # Cálculo de NDMI excluyendo ceros
                mask = (arr_b5 != 0) & (arr_b6 != 0) & np.isfinite(arr_b5) & np.isfinite(arr_b6)
                den = arr_b5 + arr_b6
                ndmi_arr = np.full(arr_b5.shape, -9999.0, dtype=np.float32)
                valid_den = mask & (den != 0)
                ndmi_arr[valid_den] = (arr_b5[valid_den] - arr_b6[valid_den]) / den[valid_den]

                valid_data = valid_den & (ndmi_arr >= -1.0) & (ndmi_arr <= 1.0)
                if not np.any(valid_data):
                    st.error("No hay píxeles válidos dentro del polígono evaluado.")
                    st.stop()

                ha_px = abs(out_transform_b5[0] * out_transform_b5[4]) / 10000.0
                vals = ndmi_arr[valid_data]
                p33, p66 = np.percentile(vals, 33), np.percentile(vals, 66)

                ph_cat = np.zeros(ndmi_arr.shape, dtype=np.uint8)
                ph_cat[valid_data & (ndmi_arr <= p33)] = 1
                ph_cat[valid_data & (ndmi_arr > p33) & (ndmi_arr <= p66)] = 2
                ph_cat[valid_data & (ndmi_arr > p66)] = 3

                # Guardar Ráster Clasificado de pH en GeoTIFF
                raster_output_path = os.path.join(temp_dir, "mapa_ph_clasificado.tif")
                meta.update({
                    "driver": "GTiff",
                    "height": ph_cat.shape[0],
                    "width": ph_cat.shape[1],
                    "transform": out_transform_b5,
                    "count": 1,
                    "dtype": "uint8",
                    "nodata": 0
                })
                with rasterio.open(raster_output_path, "w", **meta) as dst:
                    dst.write(ph_cat, 1)

                # 4. Generación de Centroides Vectoriales
                rows, cols = np.where(ph_cat > 0)
                points_data = []
                
                for row, col in zip(rows, cols):
                    clase = int(ph_cat[row, col])
                    x = out_transform_b5[2] + (col + 0.5) * out_transform_b5[0]
                    y = out_transform_b5[5] + (row + 0.5) * out_transform_b5[4]
                    pt = Point(x, y)
                    
                    nombre_clase_map = {1: "Ácido (< 5.5)", 2: "Neutro (5.5 - 6.8)", 3: "Alcalino (> 6.8)"}
                    
                    points_data.append({
                        "geometry": pt,
                        "PH_CLASE": clase,
                        "PH_NOMBRE": nombre_clase_map.get(clase, "N/D")
                    })

                gdf_points = gpd.GeoDataFrame(points_data, crs=src_b5.crs)
                
                # Guardar rutas y datos en la sesión para persistencia en descargas
                st.session_state['gdf_points'] = gdf_points
                st.session_state['raster_output_path'] = raster_output_path
                st.session_state['temp_dir'] = temp_dir
                st.session_state['processed'] = True

                # Estadísticas
                c1 = int(np.sum(ph_cat == 1))
                c2 = int(np.sum(ph_cat == 2))
                c3 = int(np.sum(ph_cat == 3))
                total_px = c1 + c2 + c3
                
                st.session_state['stats'] = {
                    'h_acid': c1 * ha_px, 'p_acid': (c1 / total_px) * 100,
                    'h_neut': c2 * ha_px, 'p_neut': (c2 / total_px) * 100,
                    'h_alca': c3 * ha_px, 'p_alca': (c3 / total_px) * 100,
                    'total_ha': (c1 + c2 + c3) * ha_px,
                    'fecha': datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                
                st.success("¡Modelo ejecutado con éxito!")

            except Exception as e:
                st.error(f"Ocurrió un error durante el procesamiento: {e}")

    # Mostrar resultados si ya se procesó
    if st.session_state.get('processed', False):
        stats = st.session_state['stats']
        gdf_points = st.session_state['gdf_points']
        raster_output_path = st.session_state['raster_output_path']
        temp_out = st.session_state.get('temp_dir', tempfile.mkdtemp())

        st.markdown("### 📊 Resultados y Superficies de Suelos")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Superficie Total", f"{stats['total_ha']:.2f} Ha")
        col2.metric("Ácido (< 5.5)", f"{stats['h_acid']:.2f} Ha", f"{stats['p_acid']:.1f}%")
        col3.metric("Neutro (5.5 - 6.8)", f"{stats['h_neut']:.2f} Ha", f"{stats['p_neut']:.1f}%")
        col4.metric("Alcalino (> 6.8)", f"{stats['h_alca']:.2f} Ha", f"{stats['p_alca']:.1f}%")

        # Visualización en Folium
        st.markdown("### 🗺️ Visor Geográfico de Puntos Estimados")
        gdf_map = gdf_points.to_crs("EPSG:4326")
        
        if len(gdf_map) > 2000:
            gdf_map = gdf_map.sample(2000)

        m = folium.Map(location=[gdf_map.geometry.y.mean(), gdf_map.geometry.x.mean()], zoom_start=15)
        
        color_map = {1: "#ef4444", 2: "#22c55e", 3: "#3b82f6"}
        for _, row in gdf_map.iterrows():
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=3,
                color=color_map.get(row['PH_CLASE'], "#333"),
                fill=True,
                fill_color=color_map.get(row['PH_CLASE'], "#333"),
                fill_opacity=0.8,
                popup=f"Clase: {row['PH_NOMBRE']}"
            ).add_to(m)

        st_folium(m, width=900, height=450)

        # Panel de Descargas y Reportes
        st.markdown("### 📥 Panel de Descarga de Archivos e Informes Técnicos")
        
        # Generar Reporte Word (.docx)
        doc = Document()
        if os.path.exists("logo.png"):
            doc.add_picture("logo.png", width=Inches(1.5))
        doc.add_heading('Syntro Academy - Informe Técnico de Suelos', 0)
        doc.add_paragraph(f"Fecha de generación: {stats['fecha']}")
        doc.add_paragraph("Modelo de Estimación Espacial de pH basado en Criterio Espectral de Sensores Remotos.")
        
        doc.add_heading('Resumen de Superficies Evaluadas', level=1)
        doc.add_paragraph(f"• Superficie Total Analizada: {stats['total_ha']:.2f} Hectáreas")
        doc.add_paragraph(f"• Suelos Ácidos (< 5.5): {stats['h_acid']:.2f} Ha ({stats['p_acid']:.1f}%)")
        doc.add_paragraph(f"• Suelos Neutros (5.5 - 6.8): {stats['h_neut']:.2f} Ha ({stats['p_neut']:.1f}%)")
        doc.add_paragraph(f"• Suelos Alcalinos (> 6.8): {stats['h_alca']:.2f} Ha ({stats['p_alca']:.1f}%)")
        
        doc_path = os.path.join(temp_out, "Informe_Tecnico_pH.docx")
        doc.save(doc_path)

        # Rutas de archivos vectoriales
        geojson_path = os.path.join(temp_out, "puntos_ph.geojson")
        if not os.path.exists(geojson_path):
            gdf_points.to_file(geojson_path, driver="GeoJSON")

        kml_path = os.path.join(temp_out, "puntos_ph.kml")
        if not os.path.exists(kml_path):
            kml = simplekml.Kml()
            for _, row in gdf_points.to_crs("EPSG:4326").iterrows():
                pnt = kml.newpoint(name=str(row['PH_NOMBRE']), coords=[(row.geometry.x, row.geometry.y)])
                pnt.description = f"Clase de pH: {row['PH_NOMBRE']}"
            kml.save(kml_path)

        zip_shp_path = os.path.join(temp_out, "puntos_ph_shp.zip")
        if not os.path.exists(zip_shp_path):
            shp_dir = os.path.join(temp_out, "shapefile")
            os.makedirs(shp_dir, exist_ok=True)
            gdf_points.to_file(os.path.join(shp_dir, "puntos_ph.shp"), driver="ESRI Shapefile")
            with zipfile.ZipFile(zip_shp_path, 'w') as zipf:
                for root, _, files in os.walk(shp_dir):
                    for file in files:
                        zipf.write(os.path.join(root, file), file)

        # Botones de descarga leídos estrictamente como bytes para forzar las extensiones reales (.tif, .docx, etc.)
        dcol1, dcol2, dcol3, dcol4, dcol5 = st.columns(5)
        
        with dcol1:
            if os.path.exists(doc_path):
                with open(doc_path, "rb") as f:
                    st.download_button("📄 Informe Word", data=f.read(), file_name="Informe_pH_Syntro.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        with dcol2:
            if os.path.exists(raster_output_path):
                with open(raster_output_path, "rb") as f:
                    st.download_button("🗺️️ Ráster .TIF", data=f.read(), file_name="mapa_ph_clasificado.tif", mime="image/tiff")

        with dcol3:
            if os.path.exists(geojson_path):
                with open(geojson_path, "rb") as f:
                    st.download_button("📥 GeoJSON", data=f.read(), file_name="puntos_ph_syntro.geojson", mime="application/json")

        with dcol4:
            if os.path.exists(kml_path):
                with open(kml_path, "rb") as f:
                    st.download_button("🌎 KML Earth", data=f.read(), file_name="puntos_ph_syntro.kml", mime="application/vnd.google-earth.kml+xml")

        with dcol5:
            if os.path.exists(zip_shp_path):
                with open(zip_shp_path, "rb") as f:
                    st.download_button("🗂 Shapefile .ZIP", data=f.read(), file_name="puntos_ph_shapefile.zip", mime="application/zip")

else:
    st.info("👈 Por favor, carga tu archivo ZIP con las bandas recortadas (B5 y B6 en TIF) y tu perímetro vectorial en la barra lateral para iniciar.")
