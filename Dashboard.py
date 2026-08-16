# Inicio.py
# Dashboard financiero - Home / Resumen
# Ejecutar con: streamlit run Inicio.py

import streamlit as st
import plotly.express as px
import pandas as pd

from data_layer import actualizar_datos_si_corresponde, cargar_datos_gold
from logic_layer import (
    calcular_indice_banco,
    calcular_rentabilidad_normalizada_por_producto,
    calcular_kpis,
)

APP_TITULO = "Conoce qué producto financiero te conviene más"


# ============================================================
# CAPA DE VISUALIZACIÓN
# ============================================================

def render_config() -> None:
    """Configura la página principal. Sin parámetros. Retorna: None."""
    st.set_page_config(
        page_title="Dashboard Financiero",
        page_icon="💰",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def render_header() -> None:
    """Renderiza el encabezado principal."""

    st.markdown(
        """
        <div style="padding:25px;border-radius:15px;background:#f5f7fa">

        <h1>💰 Comparador de Productos Financieros</h1>

        <p style="font-size:18px;">
        Explora la rentabilidad, los costos y los beneficios de las principales
        cuentas de ahorro, depósitos a plazo y tarjetas de crédito del mercado peruano.
        </p>

        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.info("🏦 Cuentas de ahorro")

    with col2:
        st.info("📈 Depósitos a plazo")

    with col3:
        st.info("💳 Tarjetas de crédito")

    st.divider()


def render_kpis(kpis: dict) -> None:
    """
    Renderiza las tarjetas KPI.
    """

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
                f"""
                <div style="padding:20px;border-radius:15px;border:1px solid #e6e6e6;">
                    <h4>🏆 Producto con Mejor TREA</h4>
                    <h2>{kpis['mejor_trea']['trea']:.2f}%</h2>
                    <p>
                        <strong>{kpis['mejor_trea']['producto']}</strong><br>
                        {kpis['mejor_trea']['banco']}
                    </p>
                    <p>
                        📈 {kpis['mejor_trea']['multiplo']:.1f} veces superior
                        al promedio del mercado.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

        with st.expander("ℹ️ ¿Qué es la TREA?"):

            st.markdown(
                """
                La **TREA (Tasa de Rendimiento Efectivo Anual)** representa la
                rentabilidad real obtenida en un año.

                El indicador se calcula utilizando el producto con la mayor
                rentabilidad entre las cuentas de ahorro y los depósitos a plazo.
                """
            )

    with c2:

        st.markdown(
            f"""
            <div style="padding:20px;border-radius:15px;border:1px solid #e6e6e6;">
                <h4>🥇 Banco líder</h4>
                <h2>{kpis['banco_lider']['banco']}</h2>
                <p>
                    Índice de desempeño:
                    <strong>{kpis['banco_lider']['indice']*100:.1f}%</strong>
                </p>
                <p>
                    📊 Mejor equilibrio entre rentabilidad y accesibilidad.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        with st.expander("ℹ️ ¿Cómo se calcula?"):

            st.markdown(
                """
                **Índice del banco**

                - 50 % rentabilidad.
                - 50 % accesibilidad.

                **Rentabilidad:** promedio de la TREA de cuentas de ahorro y
                depósitos a plazo.

                **Accesibilidad:** porcentaje de productos con costo cero.
                """
            )

    with c3:

        st.markdown(
            f"""
            <div style="padding:20px;border-radius:15px;border:1px solid #e6e6e6;">
                <h4>💳 TC más rentable</h4>
                <h2>S/ {kpis['tc_top']['valor']:,.0f}</h2>
                <p>
                    <strong>{kpis['tc_top']['tarjeta']}</strong><br>
                    {kpis['tc_top']['banco']}
                </p>
                <p>
                    ✨ Mayor beneficio económico anual.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        with st.expander("ℹ️ ¿Qué significa 'rentable'?"):

            st.markdown(
                """
                El indicador utilizado es el
                **valor neto anual recurrente**.

                Este valor considera:

                - Millas o puntos acumulados.
                - Beneficios asociados.
                - Costo de la membresía.

                El resultado representa el beneficio económico anual esperado.
                """
            )


def render_grafico_rentabilidad_producto(indice_banco: pd.DataFrame) -> None:
    """
    Renderiza el gráfico de dispersión de rentabilidad vs accesibilidad por banco.
    Parámetros: indice_banco (pd.DataFrame) resultado de calcular_indice_banco().
    Retorna: None — efecto visual directo en Streamlit.
    """
    st.subheader("📊 Rentabilidad vs accesibilidad por banco")

    fig = px.scatter(
        indice_banco,
        x="accesibilidad_norm",
        y="rentabilidad_norm",
        size="indice_banco",
        text="banco",
        hover_data=[
            "rentabilidad_promedio",
            "accesibilidad",
            "indice_banco"
        ],
        title="Rentabilidad vs accesibilidad por banco",
        labels={
            "accesibilidad_norm": "Accesibilidad",
            "rentabilidad_norm": "Rentabilidad"
        }
    )

    fig.update_traces(
        textposition="top center"
    )

    fig.update_layout(
        plot_bgcolor="white",
        height=600
    )

    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "El tamaño del punto representa el índice global del banco "
        "(50% rentabilidad + 50% accesibilidad)."
    )


def render_navegacion() -> None:
    """Muestra accesos a las páginas de detalle por producto. Sin parámetros. Retorna: None."""
    st.divider()
    st.caption(
        "👉 Usa el menú lateral para ver el detalle de **Cuentas de Ahorro**, "
        "**Depósitos a Plazo** y **Tarjetas de Crédito**."
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """Orquesta el home: ETL trigger, carga, lógica y visualización. Retorna: None."""
    render_config()

    # --- Capa de datos ---
    actualizar_datos_si_corresponde()
    cuentas_df, dpf_df, tc_df = cargar_datos_gold()

    render_header()

    # --- Capa de lógica ---
    indice_banco = calcular_indice_banco(cuentas_df, dpf_df)
    df_rentabilidad = calcular_rentabilidad_normalizada_por_producto(cuentas_df, dpf_df, tc_df)
    kpis = calcular_kpis(cuentas_df, dpf_df, tc_df, indice_banco)

    # --- Capa de visualización ---
    render_kpis(kpis)
    st.divider()
    render_grafico_rentabilidad_producto(indice_banco)
    render_navegacion()


if __name__ == "__main__":
    main()