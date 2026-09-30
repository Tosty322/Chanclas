# -------------------------------------------------------------
# REPOSICIÓN DE MERCADERÍA
# -------------------------------------------------------------
elif menu == "Reposición de Mercadería":
    st.header("🔄 Reposición y Alerta de Stock Bajo")
    engine = conectar_db()

    # Selector para definir qué consideramos "stock bajo"
    limite_stock = st.slider("Mostrar productos con stock menor o igual a:", min_value=1, max_value=20, value=5)

    # Consultar productos que cumplan con la condición de stock bajo
    query_stock = f"SELECT id, codigo_interno, nombre, categoria, talla, stock, precio_compra FROM productos WHERE stock <= {limite_stock} ORDER BY stock ASC"
    df_reposicion = pd.read_sql(query_stock, engine)

    if df_reposicion.empty:
        st.success(f"🎉 ¡Todo en orden! No hay sandalias con stock menor o igual a {limite_stock} unidades.")
    else:
        st.warning(f"⚠️ Se encontraron {lenf := len(df_reposicion)} productos con stock bajo o agotado.")
        
        # Mostrar tabla resumida de alerta
        st.dataframe(df_reposicion[["codigo_interno", "nombre", "categoria", "talla", "stock", "precio_compra"]], use_container_width=True)

        st.divider()
        st.subheader("📥 Registrar Ingreso de Mercadería (Repostar)")

        # Formulario para recargar stock
        with st.form("form_reposicion"):
            df_reposicion["opcion_rep"] = df_reposicion["nombre"] + " [Talla: " + df_reposicion["talla"] + "] - Stock Actual: " + df_reposicion["stock"].astype(str)
            prod_a_reponer = st.selectbox("Selecciona la sandalia que llegó del proveedor:", df_reposicion["opcion_rep"])
            
            cantidad_nueva = st.number_input("Cantidad de unidades que ingresan al almacén:", min_value=1.0, value=10.0, format="%.2f")
            
            btn_reponer = st.form_submit_button("Actualizar y Sumar al Stock")

            if btn_reponer:
                # Obtener el ID del producto seleccionado
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
