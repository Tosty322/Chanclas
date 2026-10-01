from datetime import datetime
from io import BytesIO
import pandas as pd
from PIL import Image
import streamlit as st
from sqlalchemy import create_engine, text
from supabase import create_client


# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Sistema de Ventas - Sandalias", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILO VISUAL PERSONALIZADO (CSS) ---
st.markdown("""
    <style>
    /* Ocultar únicamente el pie de página predeterminado de Streamlit */
    footer {visibility: hidden;}

    /* Estilo general para los títulos */
    h1, h2, h3 {
        color: #1E3A8A; /* Azul corporativo oscuro */
        font-family: 'Helvetica Neue', sans-serif;
    }

    /* Estilo moderno para los botones principales */
    div.stButton > button {
        background-color: #2563EB;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    div.stButton > button:hover {
        background-color: #1D4ED8;
        border-color: #1D4ED8;
    }

    /* Estilo para las filas de productos (Diseño en lista horizontal) */
    .product-row {
        background-color: #ffffff;
        border: 1px solid #E5E7EB;
        border-radius: 10px;
        padding: 12px 16px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
        margin-bottom: 12px;
        display: flex;
        align-items: center;
    }
    .product-title {
        font-size: 16px;
        font-weight: bold;
        color: #1F2937;
        margin-bottom: 2px;
    }
    .product-info {
        font-size: 13px;
        color: #6B7280;
    }
    .product-notes {
        font-size: 12px;
        color: #4B5563;
        background-color: #F3F4F6;
        padding: 4px 8px;
        border-radius: 6px;
        margin-top: 4px;
        border-left: 3px solid #2563EB;
    }
    .product-price {
        font-size: 18px;
        font-weight: bold;
        color: #2563EB;
    }
    </style>
""", unsafe_allow_html=True)


# --- CONEXIÓN DIRECTA A SUPABASE (POSTGRESQL) ---
def conectar_db():
    db_url = st.secrets["connections"]["postgresql"]["url"]
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    
    engine = create_engine(db_url)
    return engine

# --- CONEXIÓN A SUPABASE (STORAGE) ---
def conectar_supabase_storage():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Faltan las credenciales de Supabase en st.secrets: {e}")
        return None


# --- COMPRESIÓN DE IMÁGENES (Límite máx. aprox. 80 KB) ---
def comprimir_imagen(imagen_subida, max_ancho=600, calidad=65):
    img = Image.open(imagen_subida)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    if img.width > max_ancho:
        proporcion = max_ancho / img.width
        nuevo_alto = int(img.height * proporcion)
        img = img.resize((max_ancho, nuevo_alto), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=calidad, optimize=True)
    
    if buffer.getbuffer().nbytes > 80 * 1024:
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=50, optimize=True)

    buffer.seek(0)
    return buffer


# --- SUBIR A BUCKET ---
def subir_a_supabase(file_buffer, nombre_archivo, carpeta):
    supabase = conectar_supabase_storage()
    if not supabase:
        return None
    try:
        path = f"{carpeta}/{nombre_archivo}"
        supabase.storage.from_("archivos-chanclas").upload(
            path, file_buffer.getvalue(), file_options={"content-type": "image/jpeg", "upsert": "true"}
        )
        return supabase.storage.from_("archivos-chanclas").get_public_url(path)
    except Exception as e:
        try:
            return supabase.storage.from_("archivos-chanclas").get_public_url(path)
        except Exception as err:
            st.error(f"Error al subir imagen: {err}")
            return None


# --- FUNCIÓN AUXILIAR PARA FORMATEAR STOCK ---
def formatear_stock(total_unidades):
    total_unidades = int(round(total_unidades))
    docenas = total_unidades // 12
    unidades = total_unidades % 12
    return f"{docenas} doc. y {unidades} un."


# --- MENÚ DE NAVEGACIÓN ---
st.title("🩴 Sistema de Control y Ventas - Sandalias")
st.sidebar.title("Menú de Navegación")

menu = st.sidebar.selectbox(
    "Seleccione una opción",
    [
        "Inventario Actual",
        "Registrar Modelo",
        "Registrar Venta (POS)",
        "Historial de Ventas",
        "Reposición de Mercadería",
        "Eliminar Modelo",
    ],
)

# -------------------------------------------------------------
# 1. INVENTARIO ACTUAL
# -------------------------------------------------------------
if menu == "Inventario Actual":
    engine = conectar_db()
    st.header("📦 Inventario y Modelos Registrados")

    busqueda_inv = st.text_input("🔍 Buscar modelo por nombre o código:")
    
    # Consulta segura usando parámetros para evitar errores de sintaxis o SQL injection
    if busqueda_inv:
        query = text("SELECT * FROM productos WHERE nombre ILIKE :busqueda OR codigo_interno ILIKE :busqueda ORDER BY id DESC")
        df_productos = pd.read_sql(query, engine, params={"busqueda": f"%{busqueda_inv}%"})
    else:
        query = text("SELECT * FROM productos ORDER BY id DESC")
        df_productos = pd.read_sql(query, engine)

    if "foto_url" in df_productos.columns:
        df_productos["foto_url"] = df_productos["foto_url"].fillna("").astype(str)
        df_productos.loc[df_productos["foto_url"].isin(["0", "None", "nan", "NaN", "null"]), "foto_url"] = ""
    
    if "origen" in df_productos.columns:
        df_productos["origen"] = df_productos["origen"].fillna("Nacional").astype(str)
    else:
        df_productos["origen"] = "Nacional"

    if "apuntes" in df_productos.columns:
        df_productos["apuntes"] = df_productos["apuntes"].fillna("").astype(str)
        df_productos.loc[df_productos["apuntes"].isin(["None", "nan", "NaN", "null"]), "apuntes"] = ""
    else:
        df_productos["apuntes"] = ""

    if df_productos.empty:
        st.info("No hay modelos registrados.")
    else:
        for _, row in df_productos.iterrows():
            with st.container(border=True):
                col_info1, col_info2, col_info3, col_info4, col_img = st.columns([2.5, 1.8, 1.5, 1.5, 1.2])
                
                stock_texto = formatear_stock(row['stock'])

                with col_info1:
                    st.markdown(f"<div class='product-title'>{row['nombre']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='product-info'>Código: <b>{row['codigo_interno']}</b></div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='product-info'>Categoría: <b>{row['categoria']}</b></div>", unsafe_allow_html=True)

                with col_info2:
                    st.markdown(f"<div class='product-info'>Talla: <b>{row['talla']}</b></div>", unsafe_allow_html=True)
                    origen_badge = "🟢 Nacional" if row['origen'] == "Nacional" else "🔵 Internacional"
                    st.markdown(f"<div class='product-info'>Origen: <b>{origen_badge}</b></div>", unsafe_allow_html=True)

                with col_info3:
                    st.markdown(f"<div class='product-info'>Stock:<br><b>{stock_texto}</b></div>", unsafe_allow_html=True)

                with col_info4:
                    st.markdown(f"<div class='product-price'>S/ {row['precio_venta']:.2f}</div>", unsafe_allow_html=True)
                    st.caption(f"Costo: S/ {row['precio_compra']:.2f}")

                with col_img:
                    url_foto = row.get("foto_url", "").strip()
                    if url_foto.startswith("http") and len(url_foto) > 10:
                        try:
                            st.image(url_foto, width=80)
                        except Exception:
                            st.caption("Sin foto")
                    else:
                        st.caption("Sin foto")

                if row['apuntes'].strip():
                    st.markdown(f"<div class='product-notes'>📝 <b>Apunte:</b> {row['apuntes']}</div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. REGISTRAR PRODUCTO
# -------------------------------------------------------------
elif menu == "Registrar Modelo":
    st.header("➕ Registrar Nuevo Modelo")

    with st.form("form_producto"):
        col1, col2 = st.columns(2)
        with col1:
            codigo = st.text_input("Código Interno (Ej: SAN-001)")
            nombre = st.text_input("Nombre / Modelo (Ej: Modelo Anatómico de Cuero)")
            categoria = st.selectbox(
                "Categoría",
                ["Dama", "Caballero", "Niño", "Niña", "Juvenil"],
            )
            origen = st.selectbox("Origen del Producto", ["Nacional", "Internacional"])
        with col2:
            talla = st.text_input("Talla (Ej: 36, 37, 38 o Rango 36-39)")
            
            st.markdown("<b>📦 Stock Inicial (Ingrese el total de unidades sueltas):</b>", unsafe_allow_html=True)
            stock_inicial_unidades = st.number_input("Cantidad total de unidades", min_value=0, value=12, step=1)
            
            doc_prev = stock_inicial_unidades // 12
            und_prev = stock_inicial_unidades % 12
            st.info(f"💡 Equivale a: **{doc_prev} docenas y {und_prev} unidades**")

            precio_venta = st.number_input("Precio de Venta por Docena (S/)", min_value=0.0, format="%.2f")
            precio_compra = st.number_input("Precio de Compra / Costo por Docena (S/)", min_value=0.0, format="%.2f")
            
        apuntes = st.text_area("Apuntes u Observaciones (Opcional)", placeholder="Ej: Material sintético importado de Brasil, horma pequeña...")
        foto_subida = st.file_uploader("Foto del Modelo", type=["jpg", "jpeg", "png", "webp"])

        submit = st.form_submit_button("Guardar Modelo")

        if submit:
            if codigo and nombre:
                foto_url = ""
                if foto_subida is not None:
                    with st.spinner("Subiendo foto..."):
                        img_comp = comprimir_imagen(foto_subida)
                        nombre_archivo = f"modelo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        foto_url = subir_a_supabase(img_comp, nombre_archivo, "inventario")

                try:
                    engine = conectar_db()
                    with engine.begin() as conn:
                        conn.execute(
                            text("""
                                INSERT INTO productos (codigo_interno, nombre, categoria, origen, talla, stock, precio_venta, precio_compra, foto_url, apuntes)
                                VALUES (:codigo, :nombre, :categoria, :origen, :talla, :stock, :precio_venta, :precio_compra, :foto_url, :apuntes)
                            """),
                            dict(
                                codigo=codigo,
                                nombre=nombre,
                                categoria=categoria,
                                origen=origen,
                                talla=talla,
                                stock=float(stock_inicial_unidades),
                                precio_venta=precio_venta,
                                precio_compra=precio_compra,
                                foto_url=foto_url,
                                apuntes=apuntes,
                            ),
                        )
                    st.success(f"¡Modelo '{nombre}' registrado con éxito! (Stock: {formatear_stock(stock_inicial_unidades)})")
                except Exception as e:
                    st.error(f"Error al registrar (el código ya podría existir): {e}")
            else:
                st.warning("Completa al menos el código y el nombre.")

# -------------------------------------------------------------
# 3. REGISTRAR VENTA (POS)
# -------------------------------------------------------------
elif menu == "Registrar Venta (POS)":
    st.header("🛒 Caja / Punto de Venta")
    engine = conectar_db()

    filtro_pos = st.text_input("🔍 Buscar modelo para vender:")
    if filtro_pos:
        query_pos = text("SELECT id, codigo_interno, nombre, talla, stock, precio_venta FROM productos WHERE (nombre ILIKE :busqueda OR codigo_interno ILIKE :busqueda) AND stock > 0")
        df_productos = pd.read_sql(query_pos, engine, params={"busqueda": f"%{filtro_pos}%"})
    else:
        query_pos = text("SELECT id, codigo_interno, nombre, talla, stock, precio_venta FROM productos WHERE stock > 0")
        df_productos = pd.read_sql(query_pos, engine)

    if df_productos.empty:
        st.warning("No hay modelos con stock disponible.")
    else:
        if "carrito_chanclas" not in st.session_state:
            st.session_state.carrito_chanclas = []

        df_productos["stock_texto"] = df_productos["stock"].apply(formatear_stock)
        df_productos["opcion_pos"] = (
            df_productos["nombre"]
            + " [Talla: " + df_productos["talla"]
            + "] - Stock: " + df_productos["stock_texto"]
            + " - S/ " + df_productos["precio_venta"].astype(str) + " por doc."
        )

        col_select, col_cant = st.columns([2.5, 1.5])
        with col_select:
            prod_elegido = st.selectbox("Selecciona el modelo:", df_productos["opcion_pos"])
        
        idx_sel = df_productos[df_productos["opcion_pos"] == prod_elegido].index[0]
        precio_docena_actual = float(df_productos.loc[idx_sel, "precio_venta"])

        with col_cant:
            cantidad_docenas = st.number_input(
                "Docenas a vender (Ej: 0.5 = 6 un, 1 = 1 doc)", 
                min_value=0.0833, 
                value=1.00, 
                step=0.25, 
                format="%.4f"
            )

        subtotal_calculado = cantidad_docenas * precio_docena_actual
        unidades_equivalentes = int(round(cantidad_docenas * 12))
        
        st.info(f"💡 **Resumen:** {cantidad_docenas} docena(s) equivalen a **{unidades_equivalentes} unidades** | Precio Docena: **S/ {precio_docena_actual:.2f}** | **Subtotal Parcial: S/ {subtotal_calculado:.2f}**")

        if st.button("➕ Agregar al Carrito"):
            p_id = df_productos.loc[idx_sel, "id"]
            p_nombre = df_productos.loc[idx_sel, "nombre"]
            p_stock = df_productos.loc[idx_sel, "stock"]

            unidades_a_vender = cantidad_docenas * 12.0

            if unidades_a_vender > p_stock:
                st.error(f"Stock insuficiente. Disponible: {formatear_stock(p_stock)}.")
            else:
                st.session_state.carrito_chanclas.append({
                    "id": int(p_id),
                    "nombre": p_nombre,
                    "cantidad_doc": float(cantidad_docenas),
                    "cantidad_unidades": float(unidades_a_vender),
                    "precio_docena": float(precio_docena_actual),
                    "subtotal": float(subtotal_calculado),
                })
                st.success(f"Agregado al carrito: {p_nombre} ({unidades_equivalentes} un.)")

        if st.session_state.carrito_chanclas:
            st.subheader("🛍 Carrito Actual")
            df_carrito = pd.DataFrame(st.session_state.carrito_chanclas)
            
            df_carrito_display = df_carrito[["nombre", "cantidad_doc", "precio_docena", "subtotal"]].copy()
            df_carrito_display.columns = ["Modelo", "Docenas Vendidas", "Precio x Docena (S/)", "Subtotal Parcial (S/)"]
            st.dataframe(df_carrito_display, use_container_width=True)

            total_original = df_carrito["subtotal"].sum()
            st.markdown(f"### Total General a Cobrar: **S/ {total_original:.2f}**")

            # --- OPCIONES DE COMPROBANTE Y PAGO ---
            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                tipo_comprobante = st.selectbox("Tipo de Comprobante", ["Boleta", "Factura", "Nota de Venta"])
            with col_p2:
                numero_comprobante = st.text_input("N° de Talonario / Comprobante", placeholder="Ej: B001-00123")
            with col_p3:
                metodo_pago = st.selectbox("Método de pago", ["Efectivo", "Yape / Plin", "Tarjeta"])

            monto_yape = 0.0
            monto_efectivo = 0.0
            if metodo_pago == "Yape / Plin":
                monto_yape = total_original
            else:
                monto_efectivo = total_original

            boleta_subida = st.file_uploader("Foto de la Boleta / Comprobante (Opcional)", type=["jpg", "jpeg", "png", "webp"])

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("✅ Confirmar Venta"):
                    boleta_url = ""
                    if boleta_subida is not None:
                        with st.spinner("Subiendo comprobante..."):
                            img_comp = comprimir_imagen(boleta_subida)
                            nombre_bol = f"boleta_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                            boleta_url = subir_a_supabase(img_comp, nombre_bol, "boletas")

                    try:
                        fecha_venta = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        with engine.begin() as conn:
                            res = conn.execute(
                                text("""
                                    INSERT INTO ventas (fecha_hora, total, metodo_pago, monto_yape, monto_efectivo, boleta_url, tipo_comprobante, numero_comprobante)
                                    VALUES (:f_h, :tot, :m_p, :m_y, :m_e, :b_url, :t_comp, :n_comp)
                                    RETURNING id
                                """),
                                dict(
                                    f_h=fecha_venta, tot=float(total_original), m_p=metodo_pago,
                                    m_y=float(monto_yape), m_e=float(monto_efectivo), b_url=boleta_url,
                                    t_comp=tipo_comprobante, n_comp=numero_comprobante,
                                ),
                            )
                            venta_id = res.fetchone()[0]

                            for item in st.session_state.carrito_chanclas:
                                conn.execute(
                                    text("""
                                        INSERT INTO detalle_ventas (venta_id, producto_id, cantidad, precio_unitario, subtotal)
                                        VALUES (:v_id, :p_id, :cant, :p_u, :sub)
                                    """),
                                    dict(
                                        v_id=int(venta_id), p_id=int(item["id"]), cant=float(item["cantidad_doc"]),
                                        p_u=float(item["precio_docena"]), sub=float(item["subtotal"]),
                                    ),
                                )
                                conn.execute(
                                    text("UPDATE productos SET stock = stock - :cant WHERE id = :p_id"),
                                    dict(cant=float(item["cantidad_unidades"]), p_id=int(item["id"])),
                                )

                        st.success(f"¡Venta registrada con éxito! Comprobante: {tipo_comprobante} N° {numero_comprobante}")
                        st.session_state.carrito_chanclas = []
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar venta: {e}")
            with col_btn2:
                if st.button("🗑️ Vaciar Carrito"):
                    st.session_state.carrito_chanclas = []
                    st.rerun()

# -------------------------------------------------------------
# 4. HISTORIAL DE VENTAS
# -------------------------------------------------------------
elif menu == "Historial de Ventas":
    st.header("📊 Historial de Ventas y Comprobantes")
    engine = conectar_db()
    query_hist = """
        SELECT 
            v.id AS id_interno,
            v.fecha_hora,
            v.tipo_comprobante,
            v.numero_comprobante,
            p.nombre AS modelo,
            p.talla,
            dv.cantidad AS docenas_vendidas,
            dv.precio_unitario AS precio_docena,
            dv.subtotal,
            v.metodo_pago,
            v.boleta_url
        FROM detalle_ventas dv
        JOIN ventas v ON dv.venta_id = v.id
        JOIN productos p ON dv.producto_id = p.id
        ORDER BY v.id DESC
    """
    df_hist = pd.read_sql(query_hist, engine)

    if df_hist.empty:
        st.info("No hay ventas registradas.")
    else:
        df_hist["tipo_comprobante"] = df_hist["tipo_comprobante"].fillna("Nota de Venta")
        df_hist["numero_comprobante"] = df_hist["numero_comprobante"].fillna("S/N")
        
        for _, row in df_hist.iterrows():
            with st.container(border=True):
                col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 1, 1.5, 1.5, 1, 1.2, 1.5])
                
                with col1:
                    st.markdown(f"**Tipo:**<br>{row['tipo_comprobante']}", unsafe_allow_html=True)
                with col2:
                    st.markdown(f"**N°:**<br>{row['numero_comprobante']}", unsafe_allow_html=True)
                with col3:
                    st.markdown(f"**Fecha:**<br>{row['fecha_hora']}", unsafe_allow_html=True)
                with col4:
                    st.markdown(f"**Modelo / Talla:**<br>{row['modelo']} (T: {row['talla']})", unsafe_allow_html=True)
                with col5:
                    st.markdown(f"**Docenas:**<br>{row['docenas_vendidas']}", unsafe_allow_html=True)
                with col6:
                    st.markdown(f"**Subtotal:**<br>S/ {row['subtotal']:.2f}", unsafe_allow_html=True)
                with col7:
                    st.markdown("**Comprobante:**")
                    url = str(row['boleta_url']).strip()
                    if url and url not in ["", "None", "nan", "NaN", "null", "0"] and url.startswith("http"):
                        st.markdown(f"[Ver comprobante]({url})")
                    else:
                        st.markdown("<span style='color: #6B7280; font-size: 13px;'>No se adjuntó comprobante</span>", unsafe_allow_html=True)

# -------------------------------------------------------------
# 5. REPOSICIÓN DE MERCADERÍA
# -------------------------------------------------------------
elif menu == "Reposición de Mercadería":
    st.header("🔄 Reposición y Alerta de Stock Bajo")
    engine = conectar_db()

    limite_docenas = st.slider("Mostrar modelos con stock menor o igual a (en docenas):", min_value=1, max_value=20, value=5)
    limite_unidades = limite_docenas * 12.0

    query_stock = text("SELECT id, codigo_interno, nombre, categoria, talla, stock, precio_compra FROM productos WHERE stock <= :limite ORDER BY stock ASC")
    df_reposicion = pd.read_sql(query_stock, engine, params={"limite": limite_unidades})

    if df_reposicion.empty:
        st.success(f"🎉 ¡Todo en orden! No hay modelos con stock menor o igual a {limite_docenas} docenas.")
    else:
        st.warning(f"⚠️ Se encontraron {len(df_reposicion)} modelos con stock bajo.")
        
        df_reposicion["stock_formateado"] = df_reposicion["stock"].apply(formatear_stock)
        df_reposicion_display = df_reposicion[["codigo_interno", "nombre", "categoria", "talla", "stock_formateado", "precio_compra"]].copy()
        df_reposicion_display.columns = ["Código", "Modelo", "Categoría", "Talla", "Stock Actual", "Costo x Docena (S/)"]
        st.dataframe(df_reposicion_display, use_container_width=True)

        st.divider()
        st.subheader("📥 Registrar Ingreso de Mercadería (Repostar)")

        with st.form("form_reposicion"):
            df_reposicion["opcion_rep"] = df_reposicion["nombre"] + " [Talla: " + df_reposicion["talla"] + "] - Stock Actual: " + df_reposicion["stock_formateado"]
            prod_a_reponer = st.selectbox("Selecciona el modelo que llegó del proveedor:", df_reposicion["opcion_rep"])
            
            st.markdown("<b>📦 Cuánto ingresa (Ingrese el total de unidades, ej: 30):</b>", unsafe_allow_html=True)
            total_unidades_ingreso = st.number_input("Cantidad total de unidades que ingresan", min_value=0, value=12, step=1)
            
            doc_ing_prev = total_unidades_ingreso // 12
            und_ing_prev = total_unidades_ingreso % 12
            st.info(f"💡 Equivale a: **{doc_ing_prev} docenas y {und_ing_prev} unidades**")
            
            btn_reponer = st.form_submit_button("Actualizar y Sumar al Stock")

            if btn_reponer:
                idx_rep = df_reposicion[df_reposicion["opcion_rep"] == prod_a_reponer].index[0]
                id_producto = int(df_reposicion.loc[idx_rep, "id"])
                nombre_prod = df_reposicion.loc[idx_rep, "nombre"]

                try:
                    with engine.begin() as conn:
                        conn.execute(
                            text("UPDATE productos SET stock = stock + :cant WHERE id = :p_id"),
                            dict(cant=float(total_unidades_ingreso), p_id=id_producto)
                        )
                    st.success(f"✅ ¡Stock actualizado con éxito! Se sumó {formatear_stock(total_unidades_ingreso)} al modelo '{nombre_prod}'.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al actualizar el stock: {e}")

# -------------------------------------------------------------
# 6. ELIMINAR PRODUCTO
# -------------------------------------------------------------
elif menu == "Eliminar Modelo":
    st.header("🗑️ Eliminar Modelo")
    engine = conectar_db()
    df_del = pd.read_sql(text("SELECT id, codigo_interno, nombre FROM productos"), engine)

    if df_del.empty:
        st.info("No hay modelos registrados.")
    else:
        df_del["op"] = df_del["nombre"] + " [Cod: " + df_del["codigo_interno"] + "]"
        sel_del = st.selectbox("Selecciona modelo a eliminar:", df_del["op"])
        idx_d = df_del[df_del["op"] == sel_del].index[0]
        id_borrar = df_del.loc[idx_d, "id"]

        if st.button("❌ Eliminar Definitivamente", type="primary"):
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text("DELETE FROM productos WHERE id = :p_id"),
                        dict(p_id=int(id_borrar)),
                    )
                st.success("Modelo eliminado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"No se puede eliminar porque tiene historial de ventas asociado: {e}")
