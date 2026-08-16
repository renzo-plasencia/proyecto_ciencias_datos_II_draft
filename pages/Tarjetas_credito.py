import sys
from pathlib import Path

# Añadir el directorio raíz al sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

import streamlit as st
import plotly.express as px
import pandas as pd

from data_layer import actualizar_datos_si_corresponde, cargar_datos_gold
from logic_layer import obtener_metricas_tc

st.set_page_config(page_title="Tarjetas de Crédito", page_icon="💳", layout="wide")

# --- Capa de datos ---
actualizar_datos_si_corresponde()
cuentas_df, dpf_df, tc_df = cargar_datos_gold()

st.title("💳 Tarjetas de Crédito")

# Preparación de columna numérico
tc_df["valor_neto_anual_recurrente_soles"] = pd.to_numeric(
    tc_df["valor_neto_anual_recurrente_soles"], errors="coerce"
)

# --- 1. Filtro Global por Banco ---
bancos_disponibles = ["Todos"] + sorted(tc_df["banco"].dropna().unique().tolist())
banco_seleccionado = st.selectbox("🔍 Filtro de Banco", bancos_disponibles)

if banco_seleccionado != "Todos":
    tc_filtrado = tc_df[tc_df["banco"] == banco_seleccionado].copy()
else:
    tc_filtrado = tc_df.copy()

st.divider()

# Cargar métricas
metricas = obtener_metricas_tc(tc_filtrado)

# --- SECCIÓN: VALOR NETO ANUAL ---
st.subheader("VALOR NETO ANUAL RECURRENTE")
col_card, col_chart = st.columns([1, 2])

# --- 2. Card: Banco con Mejor Valor Neto Anual ---
with col_card:
    st.markdown("### Mejor Tarjeta")
    if metricas["mejor_tc"] is not None:
        top = metricas["mejor_tc"]
        st.info(
            f"""
            **{top['banco']}**  
            *{top['nombre_tarjeta']}*  
            
            # S/ {top['valor_neto_anual_recurrente_soles']:,.0f} / año
            Segmento: **{top.get('segmento_gasto', 'N/A')}**
            """
        )
    else:
        st.warning("No hay datos de tarjetas disponibles para el banco seleccionado.")

# --- 3. Valor Neto Anual por Segmento ---
with col_chart:
    st.markdown("### Valor Neto Anual por Segmento")

    segmentos_disponibles = sorted(tc_filtrado["segmento_gasto"].dropna().unique().tolist())

    # Garantizar selección por defecto de 'elite' si está disponible
    default_index = 0
    for idx, seg in enumerate(segmentos_disponibles):
        if "ELITE" in str(seg).upper():
            default_index = idx
            break

    segmento_seleccionado = st.selectbox(
        "Filtro de Segmento", 
        segmentos_disponibles, 
        index=default_index if segmentos_disponibles else 0
    )

    tc_segmento = tc_filtrado[tc_filtrado["segmento_gasto"] == segmento_seleccionado].copy()
    tc_segmento = tc_segmento.dropna(subset=["valor_neto_anual_recurrente_soles"])

    if not tc_segmento.empty:
        # 1. Crear una etiqueta única concatenando Tarjeta + Banco
        tc_segmento["tarjeta_banco"] = (
            tc_segmento["nombre_tarjeta"] + " (" + tc_segmento["banco"] + ")"
        )

        # 2. Ordenar de menor a mayor para que Plotly las dibuje de arriba hacia abajo correctamente
        tc_segmento = tc_segmento.sort_values(
            by="valor_neto_anual_recurrente_soles", ascending=True
        )

        fig_segmento = px.bar(
            tc_segmento,
            x="valor_neto_anual_recurrente_soles",
            y="tarjeta_banco",
            color="banco",
            orientation="h",
            text="valor_neto_anual_recurrente_soles",
            title=f"Ranking de Tarjetas - Segmento {segmento_seleccionado}",
            labels={
                "valor_neto_anual_recurrente_soles": "Valor Neto Anual (S/)",
                "tarjeta_banco": "Tarjeta",
                "banco": "Banco",
            },
            barmode="group",
        )

        # 3. Formato con texto más grande, en negrita y sin recorte
        fig_segmento.update_traces(
            texttemplate="<b>S/ %{text:,.0f}</b>", 
            textposition="outside",
            textfont=dict(size=26, color="#1e1e1e"),  # Tamaño de letra aumentado a 16
            cliponaxis=False
        )

        # 4. Extender el rango del eje X para dar espacio suficiente a la cifra grande
        max_val = tc_segmento["valor_neto_anual_recurrente_soles"].max()

        fig_segmento.update_layout(
            yaxis={"type": "category"},
            xaxis=dict(range=[0, max_val * 1.3]),  # 30% de espacio extra a la derecha
            height=max(450, len(tc_segmento) * 45),  # Altura por barra para evitar solapamiento
            plot_bgcolor="white",
        )

        st.plotly_chart(fig_segmento, use_container_width=True)
    else:
        st.info("No hay tarjetas para el segmento seleccionado.")


st.divider()

# --- 4. Tabla de Beneficios Principales ---
st.subheader("📋 Tabla de Beneficios Principales")

# 1. Selección de columnas idénticas al bloque de referencia
columnas_mostrar = [
    "nombre_tarjeta",
    "banco",
    "categoria",
    "beneficio_principal",
    "beneficios_clave"
]

# 2. Filtrado de columnas existentes y limpieza de nulos en tarjeta y banco
columnas_validas = [col for col in columnas_mostrar if col in tc_filtrado.columns]
tabla_beneficios = tc_filtrado[columnas_validas].dropna(subset=["nombre_tarjeta", "banco"])

# 3. Mapeo de nombres para las cabeceras visuales
renombrar_columnas = {
    "nombre_tarjeta": "Tarjeta",
    "banco": "Banco",
    "categoria": "Categoría",
    "beneficio_principal": "Beneficio Principal",
    "beneficios_clave": "Beneficios Clave"
}

# 4. Renderizado nativo en Streamlit con nombres legibles
st.dataframe(
    tabla_beneficios.rename(columns=renombrar_columnas),
    use_container_width=True,
    hide_index=True
)