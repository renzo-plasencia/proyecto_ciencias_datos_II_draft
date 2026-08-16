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
from logic_layer import obtener_metricas_dpf

st.set_page_config(page_title="Depósitos a Plazo", page_icon="📈", layout="wide")

# --- Capa de datos ---
actualizar_datos_si_corresponde()
cuentas_df, dpf_df, tc_df = cargar_datos_gold()

st.title("📈 Depósitos a Plazo Fijo")

# --- 1. Filtro por Banco ---
bancos_disponibles = ["Todos"] + sorted(dpf_df["banco"].dropna().unique().tolist())
banco_seleccionado = st.selectbox("🔍 Filtro de Banco", bancos_disponibles)

if banco_seleccionado != "Todos":
    dpf_filtrado = dpf_df[dpf_df["banco"] == banco_seleccionado].copy()
else:
    dpf_filtrado = dpf_df.copy()

st.divider()

# Cargar métricas
metricas = obtener_metricas_dpf(dpf_filtrado)

# --- SECCIÓN: TREA ---
st.subheader("TREA")
col_card, col_chart = st.columns([1, 2])

# --- 2. Banco / Producto con Mejor TREA ---
with col_card:
    st.markdown("### Mejor TREA")
    if metricas["mejor_dpf"] is not None:
        top = metricas["mejor_dpf"]
        st.info(
            f"""
            **{top['banco']}**  
            *{top['producto']}*  
            
            # {top['trea_num']:.2f}% TREA
            Monto mín: S/ {top['monto_minimo_num']:,.0f}
            """
        )
    else:
        st.warning("No hay datos disponibles para el banco seleccionado.")

# --- 3. Top 5 Ranking TREA Ordenado ---
with col_chart:
    ranking_dpf = (
        dpf_filtrado[dpf_filtrado["trea_num"] > 0][["producto", "banco", "trea_num"]]
        .sort_values(by="trea_num", ascending=False)
        .head(5)
    )
    ranking_dpf["producto_banco"] = ranking_dpf["producto"] + " (" + ranking_dpf["banco"] + ")"

    fig_ranking = px.bar(
        ranking_dpf,
        x="trea_num",
        y="producto_banco",
        orientation="h",
        text="trea_num",
        title="Top 5 Depósitos a Plazo por TREA",
        labels={"trea_num": "TREA (%)", "producto_banco": "Producto"},
    )
    fig_ranking.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    fig_ranking.update_layout(yaxis={"categoryorder": "total ascending"}, height=350)
    st.plotly_chart(fig_ranking, use_container_width=True)

st.divider()

# --- SECCIÓN: MONTO MÍNIMO REQUERIDO ---
st.subheader("MONTO MÍNIMO REQUERIDO")

dpf_valid = dpf_filtrado[dpf_filtrado["trea_num"] >= 0].copy()

if not dpf_valid.empty:
    # --- 4. Monto mínimo de apertura (Gráfico de Barras) ---
    dpf_monto_ord = dpf_valid.sort_values(by="monto_minimo_num", ascending=True)
    dpf_monto_ord["producto_banco"] = dpf_monto_ord["producto"] + " (" + dpf_monto_ord["banco"] + ")"

    fig_monto = px.bar(
        dpf_monto_ord,
        x="monto_minimo_num",
        y="producto_banco",
        orientation="h",
        text="monto_minimo_num",
        title="Monto Mínimo de Apertura por Producto (S/) — Menor barrera de entrada primero",
        labels={"monto_minimo_num": "Monto Mínimo (S/)", "producto_banco": "Producto"},
        color_discrete_sequence=["#2b5c8f"]
    )
    fig_monto.update_traces(texttemplate="S/ %{text:,.0f}", textposition="outside")
    fig_monto.update_layout(
        yaxis={"categoryorder": "array", "categoryarray": dpf_monto_ord["producto_banco"].tolist()[::-1]},
        height=400
    )
    st.plotly_chart(fig_monto, use_container_width=True)

    # --- Respuesta directa a la pregunta de negocio ---
    menor_barrera = dpf_monto_ord.iloc[0]
    st.success(
        f"🏆 **Menor barrera de entrada:** **{menor_barrera['producto']}** de "
        f"**{menor_barrera['banco']}**, con un monto mínimo de apertura de "
        f"**S/ {menor_barrera['monto_minimo_num']:,.0f}** y una TREA de "
        f"**{menor_barrera['trea_num']:.2f}%**."
    )

    st.divider()

    # --- 5. TREA vs Monto Mínimo Requerido (Scatter Plot), solo con trea > 0 para no distorsionar ---
    dpf_scatter = dpf_valid[dpf_valid["trea_num"] > 0]

    if not dpf_scatter.empty:
        fig_scatter = px.scatter(
            dpf_scatter,
            x="monto_minimo_num",
            y="trea_num",
            color="banco",
            text="producto",
            hover_data=["banco", "producto"],
            title="TREA vs Monto Mínimo Requerido en Depósitos a Plazo Fijo",
            labels={
                "monto_minimo_num": "Monto mínimo (S/)",
                "trea_num": "TREA (%)"
            }
        )
        fig_scatter.update_traces(textposition="top center")
        fig_scatter.update_layout(plot_bgcolor="white", height=500)
        st.plotly_chart(fig_scatter, use_container_width=True)

        st.caption(
            "📌 **Análisis de la relación TREA vs Monto Mínimo:** "
            "Permite evaluar la barrera de entrada de cada producto. "
            "Los productos ubicados en la esquina superior izquierda representan la mejor oportunidad, "
            "ofreciendo altas tasas de rendimiento (TREA) con un bajo capital de apertura."
        )
else:
    st.info("No hay datos de depósitos a plazo disponibles para la selección actual.")