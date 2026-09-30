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

        df_productos["stock_texto"] = df_productos["stock"].apply(formatear_stock)
        df_productos["opcion_pos"] = (
            df_productos["nombre"]
            + " [Talla: " + df_productos["talla"]
            + "] - Stock: " + df_productos["stock_texto"]
            + " - S/ " + df_productos["precio_venta"].astype(str) + " por doc."
        )

        col_select, col_cant = st.columns([2.5, 1.5])
        with col_select:
            prod_elegido = st.selectbox("Selecciona el producto:", df_productos["opcion_pos"])
        
        # Obtenemos el precio por docena del producto seleccionado actualmente para mostrarlo en tiempo real
        idx_sel = df_productos[df_productos["opcion_pos"] == prod_elegido].index[0]
        precio_docena_actual = float(df_productos.loc[idx_sel, "precio_venta"])

        with col_cant:
            # Permitimos vender por fracciones de docena (ej. 0.5 docenas = 6 unidades, o ingresando por unidades exactas divididas entre 12)
            cantidad_docenas = st.number_input(
                "Docenas a vender (Ej: 0.5 = 6 un, 1 = 1 doc)", 
                min_value=0.0833, # Aproximadamente 1 unidad (1/12)
                value=1.00, 
                step=0.25, 
                format="%.4f"
            )

        # Cálculo dinámico para mostrar alero visual al vendedor antes de agregar
        subtotal_calculado = cantidad_docenas * precio_docena_actual
        unidades_equivalentes = int(round(cantidad_docenas * 12))
        
        st.info(f"💡 **Resumen de selección:** {cantidad_docenas} docena(s) equivalen a **{unidades_equivalentes} unidades** | Precio Referencial Docena: **S/ {precio_docena_actual:.2f}** | **Subtotal a cobrar: S/ {subtotal_calculado:.2f}**")

        if st.button("➕ Agregar al Carrito"):
            p_id = df_productos.loc[idx_sel, "id"]
            p_nombre = df_productos.loc[idx_sel, "nombre"]
            p_stock = df_productos.loc[idx_sel, "stock"] # En unidades totales

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
            
            # Formateamos una vista clara para el Dataframe del carrito con ambas métricas (Precio docena y Subtotal parcial)
            df_carrito_display = df_carrito[["nombre", "cantidad_doc", "precio_docena", "subtotal"]].copy()
            df_carrito_display.columns = ["Producto", "Docenas Vendidas", "Precio x Docena (S/)", "Subtotal Parcial (S/)"]
            st.dataframe(df_carrito_display, use_container_width=True)

            total_original = df_carrito["subtotal"].sum()
            st.markdown(f"### Total General a Cobrar: **S/ {total_original:.2f}**")

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
                                        v_id=int(venta_id), p_id=int(item["id"]), cant=float(item["cantidad_doc"]),
                                        p_u=float(item["precio_docena"]), sub=float(item["subtotal"]),
                                    ),
                                )
                                conn.execute(
                                    text("UPDATE productos SET stock = stock - :cant WHERE id = :p_id"),
                                    dict(cant=float(item["cantidad_unidades"]), p_id=int(item["id"])),
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
