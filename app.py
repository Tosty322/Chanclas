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
    page_icon="🩴", 
    layout="wide"
)

# --- ESTILO GRÁFICO AVANZADO (CSS PERSONALIZADO) ---
st.markdown("""
    <style>
    /* Ocultar elementos predeterminados de Streamlit para limpiar la interfaz */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Fondo general y tipografía limpia */
    .stApp {
        background-color: #F8FAFC;
        font-family: 'Inter', sans-serif;
    }

    /* Estilo elegante para títulos principales */
    h1 {
        color: #0F172A;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    h2, h3 {
        color: #1E293B;
        font-weight: 700;
    }

    /* Tarjetas de productos y contenedores con sombra suave */
    div.stContainer, div.stForm {
        background-color: #FFFFFF;
        border-radius: 12px;
        padding: 1.2rem;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    }

    /* Botones modernos con efecto hover y colores corporativos */
    div.stButton > button {
        background-color: #2563EB;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);
        transition: all 0.2s ease-in-out;
    }
    div.stButton > button:hover {
        background-color: #1D4ED8;
        box-shadow: 0 4px 8px rgba(37, 99, 235, 0.3);
        transform: translateY(-1px);
    }

    /* Estilo de los inputs y campos de texto */
    div.stTextInput > div > div > input, div.stNumberInput > div > div > input, div.stSelectbox > div > div {
        border-radius: 8px;
        border: 1px solid #CBD5E1;
    }

    /* Barra lateral estilizada */
    section[data-testid="stSidebar"] {
        background-color: #0F172A;
    }
    section[data-testid="stSidebar"] .stMarkdown h1, 
    section[data-testid="stSidebar"] .stMarkdown h2, 
    section[data-testid="stSidebar"] .stMarkdown h3,
    section[data-testid="stSidebar"] label {
        color: #F8FAFC !important;
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


# --- COMPRESIÓN DE IMÁGENES ---
def comprimir_imagen(imagen_subida, max_ancho=800, calidad=75):
    img = Image.open(imagen_subida)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    if img.width > max_ancho:
        proporcion = max_ancho / img.width
        nuevo_alto = int(img.height * proporcion)
        img = img.resize((max_ancho, nuevo_alto), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=calidad)
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
            path, file_buffer.getvalue(), file_options={"content-type": "image/jpeg"}
        )
        return supabase.storage.from_("archivos-chanclas").get_public_url(path)
    except Exception as e:
        try:
            return supabase.storage.from_("archivos-chanclas").get_public_url(path)
        except:
            st.error(f"Error al subir imagen: {e}")
            return None


# --- MENÚ DE NAVEGACIÓN ---
st.title("🩴 Sistema de Control y Ventas - Sandalias")
st.sidebar.title("Menú Principal")

menu = st.sidebar.selectbox(
    "Seleccione una opción",
    [
        "Inventario Actual",
        "Registrar Producto",
        "Registrar Venta (POS)",
        "Historial de Ventas",
        "Reposición de Mercadería",
        "Eliminar Producto",
    ],
)

# -------------------------------------------------------------
# 1. INVENTARIO ACTUAL (ESTILO TARJETAS / GRID MODERNO)
# -------------------------------------------------------------
if menu == "Inventario Actual":
    engine = conectar_db()
    st.header("📦 Catálogo e Inventario de Sandalias")

    busqueda_inv = st.text_input("🔍 Buscar sandalia por nombre o código:")
    if busqueda_inv:
        query = f"SELECT * FROM productos WHERE nombre ILIKE '%{busqueda_inv}%' OR codigo_interno ILIKE '%{busqueda_inv}%'"
    else:
        query = "SELECT * FROM productos ORDER BY id DESC"

    df_productos = pd.read_sql(query, engine)

    if df_productos.empty:
        st.info("No hay sandalias registradas en el inventario.")
    else:
        # Mostramos los productos en una cuadrícula de 3 columnas estilo tienda online
        cols = st.columns(3)
        for index, row in df_productos.iterrows():
            with cols[index % 3]:
                with st.container():
                    if pd.notna(row["foto_url"]) and row["foto_url"]:
                        st.image(row["foto_url"], use_container_width=True)
                    else:
                        st.info("🩴 Sin imagen disponible")
                    
                    st.markdown(f"### {row['nombre']}")
                    st.caption(f"Código: {row['codigo_interno']}")
                    st.write(f"🏷️ **Cat:** {row['categoria']} | 📏 **Talla:** {row['talla']}")
                    st.write(f"📦 **Stock:** `{row['stock']} un.`")
                    st.markdown(f"💰 **Precio Venta:** S/ {row['precio_venta']:.2f}")
                    st.write(f"📉 *Costo:* S/ {row['precio_compra']:.2f}")

# -------------------------------------------------------------
# 2. REGISTRAR PRODUCTO
# -------------------------------------------------------------
elif menu == "Registrar Producto":
    st.header("➕ Registrar Nueva Sandalia")

    with st.form("form_producto"):
        col1, col2 = st.columns(2)
        with col1:
            codigo = st.text_input("Código Interno (Ej: SAN-001)")
            nombre = st.text_input("Nombre / Modelo (Ej: Sandalia Anatómica de Cuero)")
            categoria = st.selectbox(
                "Categoría",
                ["Dama", "Caballero", "Niños", "Unisex", "Playa", "Casual"],
            )
            talla = st.text_input("Talla (Ej: 36, 37, 38 o Rango 36-39)")
        with col2:
            stock = st.number_input("Stock Inicial", min_value=0.0, format="%.2f")
            precio_venta = st.number_input("Precio de Venta (S/)", min_value=0.0, format="%.2f")
            precio_compra = st.number_input("Precio de Compra / Costo (S/)", min_value=0.0, format="%.2f")
            foto_subida = st.file_uploader("Foto del Modelo", type=["jpg", "jpeg", "png", "webp"])

        submit = st.form_submit_button("Guardar Sandalia")

        if submit:
            if codigo and nombre:
                foto_url = ""
                if foto_subida is not None:
                    with st.spinner("Subiendo foto..."):
                        img_comp = comprimir_imagen(foto_subida)
                        nombre_archivo = f"sandalia_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        foto_url = subir_a_supabase(img_comp, nombre_archivo, "inventario")

                try:
                    engine = conectar_db()
                    with engine.begin() as conn:
                        conn.execute(
                            text("""
                                INSERT INTO productos (codigo_interno, nombre, categoria, talla, stock, precio_venta, precio_compra, foto_url)
                                VALUES (:codigo, :nombre, :categoria, :talla, :stock, :precio_venta, :precio_compra, :foto_url)
                            """),
                            dict(
                                codigo=codigo,
                                nombre=nombre,
                                categoria=categoria,
                                talla=talla,
                                stock=stock,
                                precio_venta=precio_venta,
                                precio_compra=precio_compra,
                                foto_url=foto_url,
                            ),
                        )
                    st.success(f"¡Sandalia '{nombre}' registrada con éxito!")
                except Exception as e:
                    st.error(f"Error al registrar (el código ya podría existir): {e}")
            else:
                st.warning("Completa al menos el código y el nombre.")

# -------------------------------------------------------------
# 3. REGISTRAR VENTA (POS)
# -------------------------------------------------------------
elif menu == "Registrar Venta (POS)":
    st.header("🛒 Caja / Punto de Venta - Sandalias")
    engine = conectar_db()

    filtro_pos = st.text_input("🔍 Buscar sandalia para vender:")
    if filtro_pos:
        query_pos = f"SELECT id, codigo_interno, nombre, talla, stock, precio_venta FROM productos WHERE (nombre ILIKE '%{filtro_pos}%' OR codigo_interno ILIKE '%{filtro_pos}%') AND stock > 0"
    else:
        query_pos = "SELECT id, codigo_interno, nombre, talla, stock, precio_venta FROM productos WHERE stock > 0"

    df_productos = pd.read_sql(query_pos, engine)

    if df_productos.empty:
        st.warning("No hay productos con stock disponible.")
    else:
        if "carrito_chanclas" not in st.session_state:
            st.session_state.carrito_chanclas = []

        df_productos["opcion_pos"] = (
            df_productos["nombre"]
            + " [Talla: " + df_productos["talla"]
            + "] - Stock: " + df_productos["stock"].astype(str)
            + " - S/ " + df_productos["precio_venta"].astype(str)
        )

        col_select, col_cant = st.columns([3, 1])
        with col_select:
            prod_elegido = st.selectbox("Selecciona el producto:", df_productos["opcion_pos"])
        with col_cant:
            idx_sel = df_productos[df_productos["opcion_pos"] == prod_elegido].index[0]
            cantidad_vender = st.number_input("Cantidad", min_value=0.01, value=1.00, format="%.2f")

        if st.button("➕ Agregar al Carrito"):
            p_id = df_productos.loc[idx_sel, "id"]
            p_nombre = df_productos.loc[idx_sel, "nombre"]
            p_stock = df_productos.loc[idx_sel, "stock"]
            p_precio = df_productos.loc[idx_sel, "precio_venta"]

            if cantidad_vender > p_stock:
                st.error(f"Stock insuficiente. Disponible: {p_stock}")
            else:
                st.session_state.carrito_chanclas.append({
                    "id": int(p_id),
                    "nombre": p_nombre,
                    "cantidad": float(cantidad_vender),
                    "precio": float(p_precio),
                    "subtotal": float(cantidad_vender * p_precio),
                })
                st.success(f"Agregado: {p_nombre}")

        if st.session_state.carrito_chanclas:
            st.subheader("🛍️ Carrito Actual")
            df_carrito = pd.DataFrame(st.session_state.carrito_chanclas)
            st.dataframe(df_carrito[["nombre", "cantidad", "precio", "subtotal"]], use_container_width=True)

            total_original = df_carrito["subtotal"].sum()
            st.write(f"Total a cobrar: **S/ {total_original:.2f}**")

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
                        with st.spinner("Subiendo boleta..."):
                            img_comp = comprimir_imagen(boleta_subida)
                            nombre_bol = f"boleta_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                            boleta_url = subir_a_supabase(img_comp, nombre_bol, "boletas")

                    try:
                        fecha_venta = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        with engine.begin() as conn:
                            res = conn.execute(
                                text("""
                                    INSERT INTO ventas (fecha_hora, total, metodo_pago, monto_yape, monto_efectivo, boleta_url)
                                    VALUES (:f_h, :tot, :m_p, :m_y, :m_e, :b_url)
                                    RETURNING id
                                """),
                                dict(
                                    f_h=fecha_venta, tot=float(total_original), m_p=metodo_pago,
                                    m_y=float(monto_yape), m_e=float(monto_efectivo), b_url=boleta_url,
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
                                        v_id=int(venta_id), p_id=int(item["id"]), cant=float(item["cantidad"]),
                                        p_u=float(item["precio"]), sub=float(item["subtotal"]),
                                    ),
                                )
                                conn.execute(
                                    text("UPDATE productos SET stock = stock - :cant WHERE id = :p_id"),
                                    dict(cant=float(item["cantidad"]), p_id=int(item["id"])),
                                )

                        st.success(f"¡Venta registrada con éxito! N° #{venta_id:04d}")
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
            v.id AS n_boleta,
            v.fecha_hora,
            p.nombre AS sandalia,
            p.talla,
            dv.cantidad,
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
        df_hist["n_boleta"] = df_hist["n_boleta"].apply(lambda x: f"#{int(x):04d}")
        st.dataframe(df_hist, use_container_width=True)

        for _, row in df_hist.iterrows():
            if pd.notna(row["boleta_url"]) and row["boleta_url"]:
                st.write(f"Boleta {row['n_boleta']} - [Ver Comprobante]({row['boleta_url']})")

# -------------------------------------------------------------
# 5. REPOSICIÓN DE MERCADERÍA
# -------------------------------------------------------------
elif menu == "Reposición de Mercadería":
    st.header("🔄 Reposición y Alerta de Stock Bajo")
    engine = conectar_db()

    limite_stock = st.slider("Mostrar productos con stock menor o igual a:", min_value=1, max_value=20, value=5)

    query_stock = f"SELECT id, codigo_interno, nombre, categoria, talla, stock, precio_compra FROM productos WHERE stock <= {limite_stock} ORDER BY stock ASC"
    df_reposicion = pd.read_sql(query_stock, engine)

    if df_reposicion.empty:
        st.success(f"🎉 ¡Todo en orden! No hay sandalias con stock menor o igual a {limite_stock} unidades.")
    else:
        st.warning(f"⚠️ Se encontraron {len(df_reposicion)} productos con stock bajo o agotado.")
        
        st.dataframe(df_reposicion[["codigo_interno", "nombre", "categoria", "talla", "stock", "precio_compra"]], use_container_width=True)

        st.divider()
        st.subheader("📥 Registrar Ingreso de Mercadería (Repostar)")

        with st.form("form_reposicion"):
            df_reposicion["opcion_rep"] = df_reposicion["nombre"] + " [Talla: " + df_reposicion["talla"] + "] - Stock Actual: " + df_reposicion["stock"].astype(str)
            prod_a_reponer = st.selectbox("Selecciona la sandalia que llegó del proveedor:", df_reposicion["opcion_rep"])
            
            cantidad_nueva = st.number_input("Cantidad de unidades que ingresan al almacén:", min_value=1.0, value=10.0, format="%.2f")
            
            btn_reponer = st.form_submit_button("Actualizar y Sumar al Stock")

            if btn_reponer:
                idx_rep = df_reposicion[df_reposicion["opcion_rep"] == prod_a_reponer].index[0]
                id_producto = int(df_reposicion.loc[idx_rep, "id"])
                nombre_prod = df_reposicion.loc[idx_rep, "nombre"]

                try:
                    with engine.begin() as conn:
                        conn.execute(
                            text("UPDATE productos SET stock = stock + :cant WHERE id = :p_id"),
                            dict(cant=float(cantidad_nueva), p_id=id_producto)
                        )
                    st.success(f"✅ ¡Stock actualizado con éxito! Se sumaron {cantidad_nueva} unidades a '{nombre_prod}'.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al actualizar el stock: {e}")

# -------------------------------------------------------------
# 6. ELIMINAR PRODUCTO
# -------------------------------------------------------------
elif menu == "Eliminar Producto":
    st.header("🗑️ Eliminar Producto")
    engine = conectar_db()
    df_del = pd.read_sql("SELECT id, codigo_interno, nombre FROM productos", engine)

    if df_del.empty:
        st.info("No hay productos.")
    else:
        df_del["op"] = df_del["nombre"] + " [Cod: " + df_del["codigo_interno"] + "]"
        sel_del = st.selectbox("Selecciona producto a eliminar:", df_del["op"])
        idx_d = df_del[df_del["op"] == sel_del].index[0]
        id_borrar = df_del.loc[idx_d, "id"]

        if st.button("❌ Eliminar Definitivamente", type="primary"):
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text("DELETE FROM productos WHERE id = :p_id"),
                        dict(p_id=int(id_borrar)),
                    )
                st.success("Producto eliminado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"No se puede eliminar porque tiene historial de ventas asociado: {e}")
