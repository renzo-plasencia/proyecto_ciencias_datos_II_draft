import sys
from pathlib import Path

# Añade la carpeta raíz (un nivel arriba de 'pages') al sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# Ahora ya puedes importar tus módulos sin problema
from data_layer import actualizar_datos_si_corresponde, cargar_datos_gold
from logic_layer import obtener_metricas_cuentas_ahorro

import streamlit as st
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="Cuentas de Ahorro", page_icon="🏦", layout="wide")

# --- Capa de datos ---
actualizar_datos_si_corresponde()
cuentas_df, dpf_df, tc_df = cargar_datos_gold()

st.title("🏦 Cuentas de Ahorro")

# --- 1. Filtro de Banco ---
bancos_disponibles = ["Todos"] + sorted(cuentas_df["banco"].dropna().unique().tolist())
banco_seleccionado = st.selectbox("🔍 Filtro de Banco", bancos_disponibles)

# Filtrar DataFrame globalmente
if banco_seleccionado != "Todos":
    cuentas_filtradas = cuentas_df[cuentas_df["banco"] == banco_seleccionado].copy()
else:
    cuentas_filtradas = cuentas_df.copy()

st.divider()

# Cargar métricas filtradas
metricas = obtener_metricas_cuentas_ahorro(cuentas_filtradas)

# --- SECCIÓN: TREA ---
st.subheader("TREA")
col_card, col_chart = st.columns([1, 2])

# --- 2. Card: Banco/Producto con Mejor TREA ---
with col_card:
    st.markdown("### Mejor TREA")
    if metricas["mejor_cuenta"] is not None:
        top = metricas["mejor_cuenta"]
        st.info(
            f"""
            **{top['banco']}**  
            *{top['producto_nombre']}*  
            
            # {top['trea_num']:.2f}% TREA
            """
        )
    else:
        st.warning("No hay datos disponibles para el banco seleccionado.")

# --- 3. Top 5 / Ranking TREA Ordenado por Producto ---
with col_chart:
    ranking_cuentas = (
        cuentas_filtradas[cuentas_filtradas["trea_num"] > 0][["producto_nombre", "banco", "trea_num"]]
        .sort_values(by="trea_num", ascending=False)
        .head(5)  # Top 5
    )
    ranking_cuentas["producto_banco"] = ranking_cuentas["producto_nombre"] + " (" + ranking_cuentas["banco"] + ")"

    fig_ranking = px.bar(
        ranking_cuentas,
        x="trea_num",
        y="producto_banco",
        orientation="h",
        text="trea_num",
        title="Top 5 Cuentas de Ahorro por TREA",
        labels={"trea_num": "TREA (%)", "producto_banco": "Producto"},
    )
    fig_ranking.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    fig_ranking.update_layout(yaxis={"categoryorder": "total ascending"}, height=350)
    st.plotly_chart(fig_ranking, use_container_width=True)

st.divider()

# --- SECCIÓN: COSTO DE MANTENIMIENTO ---
st.subheader("COSTO DE MANTENIMIENTO")

df_costos = metricas["distribucion_costos"]

if not df_costos.empty:
    # 4. Gráfico de porcentaje sin costo vs con costo
    fig_costos = px.bar(
        df_costos,
        x="porcentaje",
        y="categoria",
        orientation="h",
        text="porcentaje",
        color="categoria",
        title="Distribución de cuentas por Costo de Mantenimiento",
        labels={"porcentaje": "Porcentaje (%)", "categoria": "Categoría"},
        color_discrete_map={"Sin Costo (Gratis)": "#2ecc71", "Con Costo": "#e74c3c"}
    )
    fig_costos.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_costos.update_layout(height=300, showlegend=False)
    st.plotly_chart(fig_costos, use_container_width=True)
else:
    st.info("No se registraron datos de costo de mantenimiento.")