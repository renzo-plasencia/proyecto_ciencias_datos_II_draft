import sys
from pathlib import Path

# Añadir el directorio raíz al sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from data_layer import actualizar_datos_si_corresponde, cargar_datos_gold
from logic_layer import (
    calcular_ranking_membresia_tc,
    obtener_mejor_tarjeta_primer_sueldo,
    obtener_metricas_tc,
    obtener_tarjeta_mas_costosa,
    preparar_tc_primer_sueldo,
)

st.set_page_config(page_title="Tarjetas de Crédito", page_icon="💳", layout="wide")

# --- Capa de datos ---
actualizar_datos_si_corresponde()
cuentas_df, dpf_df, tc_df = cargar_datos_gold()

st.title("💳 Tarjetas de Crédito")

# Preparación de columna numérica
tc_df["valor_neto_anual_recurrente_soles"] = pd.to_numeric(
    tc_df["valor_neto_anual_recurrente_soles"], errors="coerce"
)


def render_grafico_membresia_tc(ranking_membresia: pd.DataFrame, tarjeta_top: pd.Series) -> None:
    """
    Renderiza el gráfico de barras del costo de membresía por tarjeta y alerta sobre la más costosa.
    """
    st.subheader("💳 Costo de membresía anual por tarjeta")

    fig = px.bar(
        ranking_membresia,
        x="nombre_tarjeta",
        y="membresia_num",
        color="banco",
        text="membresia_num",
        labels={"membresia_num": "Membresía anual (S/)", "nombre_tarjeta": "Tarjeta"},
    )
    fig.update_traces(texttemplate="S/ %{text:,.0f}", textposition="outside")
    fig.update_layout(plot_bgcolor="white", height=500, xaxis_tickangle=-40)
    st.plotly_chart(fig, use_container_width=True)

    if tarjeta_top is not None and tarjeta_top.get("membresia_num", 0) > 0:
        st.warning(
            f"⚠️ **Cuidado con el mantenimiento:** la tarjeta con mayor costo de membresía es "
            f"**{tarjeta_top['nombre_tarjeta']}** de **{tarjeta_top['banco']}**, con "
            f"**S/ {tarjeta_top['membresia_num']:,.0f}** al año. Antes de solicitarla, revisa si "
            f"cumples el requisito de exoneración (*{tarjeta_top.get('requisito_exoneracion_membresia', 'N/A')}*) "
            f"para evitar pagarla."
        )
    else:
        st.info("✅ Todas las tarjetas analizadas tienen membresía anual de S/ 0.")


# --- 1. Filtro Global por Banco ---
bancos_disponibles = ["Todos"] + sorted(tc_df["banco"].dropna().unique().tolist())
banco_seleccionado = st.selectbox("🔍 Filtro de Banco", bancos_disponibles)

# DataFrame base filtrado únicamente por banco
if banco_seleccionado != "Todos":
    tc_filtrado = tc_df[tc_df["banco"] == banco_seleccionado].copy()
else:
    tc_filtrado = tc_df.copy()

st.divider()

# Cargar métricas globales por banco (sin ser afectadas por segmento)
metricas = obtener_metricas_tc(tc_filtrado)

# --- SECCIÓN: VALOR NETO ANUAL ---
st.subheader("VALOR NETO ANUAL RECURRENTE")
col_card, col_chart = st.columns([1, 2])

# --- 2. Card: Banco con Mejor Valor Neto Anual (Afectado solo por Banco) ---
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

# --- 3. Valor Neto Anual por Segmento (Afectado por Banco y por Segmento) ---
with col_chart:
    st.markdown("### Valor Neto Anual por Segmento")

    segmentos_disponibles = sorted(tc_filtrado["segmento_gasto"].dropna().unique().tolist())

    if segmentos_disponibles:
        default_index = 0
        for idx, seg in enumerate(segmentos_disponibles):
            if "ELITE" in str(seg).upper():
                default_index = idx
                break

        # Uso de key dinámico para resetear el selectbox adecuadamente cuando cambia el banco
        segmento_seleccionado = st.selectbox(
            "Filtro de Segmento",
            segmentos_disponibles,
            index=default_index,
            key=f"select_segmento_{banco_seleccionado}"
        )

        tc_segmento = tc_filtrado[tc_filtrado["segmento_gasto"] == segmento_seleccionado].copy()
        tc_segmento = tc_segmento.dropna(subset=["valor_neto_anual_recurrente_soles"])

        if not tc_segmento.empty:
            tc_segmento["tarjeta_banco"] = (
                tc_segmento["nombre_tarjeta"] + " (" + tc_segmento["banco"] + ")"
            )
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

            fig_segmento.update_traces(
                texttemplate="<b>S/ %{text:,.0f}</b>",
                textposition="outside",
                textfont=dict(size=16, color="#1e1e1e"),
                cliponaxis=False
            )

            max_val = tc_segmento["valor_neto_anual_recurrente_soles"].max()

            fig_segmento.update_layout(
                yaxis={"type": "category"},
                xaxis=dict(range=[0, max_val * 1.3 if max_val > 0 else 1]),
                height=max(450, len(tc_segmento) * 45),
                plot_bgcolor="white",
            )

            st.plotly_chart(fig_segmento, use_container_width=True)
        else:
            st.info("No hay tarjetas para el segmento seleccionado.")
    else:
        st.info("No hay segmentos disponibles para la selección actual.")

st.divider()

# --- 4. Costo de Membresía (Afectado SOLO por filtro de Banco) ---
membresia_banco = calcular_ranking_membresia_tc(tc_filtrado)

if not membresia_banco.empty:
    # Se extrae la tarjeta más costosa sobre las tarjetas con membresía > 0 para evitar incongruencias
    tarjeta_top = membresia_banco.iloc[0]
    render_grafico_membresia_tc(membresia_banco, tarjeta_top)
else:
    st.subheader("💳 Costo de membresía anual por tarjeta")
    st.info("✅ Para el banco seleccionado, ninguna tarjeta requiere pago de membresía anual (S/ 0) o no hay datos.")

st.divider()

# --- 5. Tabla de Beneficios Principales (Afectado SOLO por filtro de Banco) ---
st.subheader("📋 Tabla de Beneficios Principales")

columnas_mostrar = [
    "nombre_tarjeta",
    "banco",
    "categoria",
    "beneficio_principal",
    "beneficios_clave"
]

columnas_validas = [col for col in columnas_mostrar if col in tc_filtrado.columns]
tabla_beneficios = (
    tc_filtrado[columnas_validas]
    .dropna(subset=["nombre_tarjeta", "banco"])
    .drop_duplicates(subset=["nombre_tarjeta", "banco"])
)

renombrar_columnas = {
    "nombre_tarjeta": "Tarjeta",
    "banco": "Banco",
    "categoria": "Categoría",
    "beneficio_principal": "Beneficio Principal",
    "beneficios_clave": "Beneficios Clave"
}

st.dataframe(
    tabla_beneficios.rename(columns=renombrar_columnas),
    use_container_width=True,
    hide_index=True
)

st.divider()

# --- 6. Primer Sueldo (Afectado SOLO por filtro de Banco) ---
st.subheader("🎓 Mejor tarjeta de entrada para primer sueldo")
st.caption("Solo se muestran tarjetas con ingreso mínimo requerido menor a S/ 3,000.")

tc_primer_sueldo = preparar_tc_primer_sueldo(tc_filtrado)

if not tc_primer_sueldo.empty:
    tc_plot = tc_primer_sueldo.sort_values("membresia_num", ascending=True).copy()

    np.random.seed(42)
    tc_plot["membresia_num_jitter"] = tc_plot["membresia_num"] + np.random.uniform(-3, 3, size=len(tc_plot))
    tc_plot["ingreso_min_num_jitter"] = tc_plot["ingreso_min_num"] + np.random.uniform(-3, 3, size=len(tc_plot))

    fig_primer_sueldo = px.scatter(
        tc_plot,
        x="ingreso_min_num_jitter",
        y="membresia_num_jitter",
        color="banco",
        hover_data=["banco", "nombre_tarjeta", "membresia_num"],
        text="nombre_tarjeta",
        title="Tarjetas de entrada (ingreso mínimo < S/3,000): ingreso vs membresía",
        labels={
            "ingreso_min_num_jitter": "Ingreso mínimo requerido (S/)",
            "membresia_num_jitter": "Membresía anual (S/)",
        },
    )
    fig_primer_sueldo.update_traces(textposition="top center")
    fig_primer_sueldo.update_layout(plot_bgcolor="white", height=550)
    st.plotly_chart(fig_primer_sueldo, use_container_width=True)

    mejor = obtener_mejor_tarjeta_primer_sueldo(tc_primer_sueldo)
    if mejor is not None:
        st.success(
            f"🏆 **Mejor tarjeta de entrada:** **{mejor['nombre_tarjeta']}** de "
            f"**{mejor['banco']}** — ingreso mínimo **S/ {mejor['ingreso_min_num']:,.0f}** "
            f"y membresía **S/ {mejor['membresia_num']:,.0f}**."
        )
else:
    st.info("No hay tarjetas con ingreso mínimo menor a S/ 3,000 en la selección actual.")