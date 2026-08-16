# data_layer.py
# Capa de datos: trigger de ETL + carga de archivos Gold
# Responsabilidad: decidir si correr el pipeline y devolver DataFrames listos

import streamlit as st
import pandas as pd
import time
from pathlib import Path
from main_etl import main

# ============================================================
# CONSTANTES
# ============================================================
RUTA_GOLD = Path("output/gold")
CACHE_TTL_MINUTOS = 30
CACHE_TTL_SEGUNDOS = CACHE_TTL_MINUTOS * 60

ARCHIVO_CUENTAS = RUTA_GOLD / "master_cuentas_ahorro.parquet"
ARCHIVO_DPF     = RUTA_GOLD / "master_plazo_fijo.parquet"
ARCHIVO_TC      = RUTA_GOLD / "master_tarjetas_credito.parquet"

ARCHIVOS_GOLD = (ARCHIVO_CUENTAS, ARCHIVO_DPF, ARCHIVO_TC)


# ============================================================
# TRIGGER DEL ETL
# ============================================================

def _existen_archivos_gold() -> bool:
    """
    Verifica si los tres archivos Gold existen en disco.
    Sin parámetros.
    Retorna: bool True si los tres archivos existen.
    """
    return all(f.exists() for f in ARCHIVOS_GOLD)


def _ejecutar_etl(mensaje: str) -> None:
    """
    Corre main_etl.main(), limpia el cache de datos y reprograma la próxima actualización.
    Parámetros: mensaje (str) texto a mostrar en el spinner.
    Retorna: None — dispara st.rerun() al finalizar.
    """
    with st.spinner(f"{mensaje} — esto puede tardar ~16 minutos..."):
        main()
    st.cache_data.clear()
    # Reprograma la próxima actualización a 30 min desde AHORA (no desde la fecha del archivo)
    st.session_state["proxima_actualizacion"] = time.time() + CACHE_TTL_SEGUNDOS
    st.rerun()


def forzar_actualizacion() -> None:
    """
    Marca la próxima actualización como vencida, para forzar el ETL en el próximo chequeo.
    Pensado para conectarse a un botón manual en el futuro.
    Sin parámetros.
    Retorna: None.
    """
    st.session_state["proxima_actualizacion"] = 0


def actualizar_datos_si_corresponde() -> None:
    """
    Ejecuta main_etl.main() solo si:
    - No existen archivos Gold (obligatorio, sin importar la sesión), o
    - Ya pasaron 30 min desde la última vez que se revisó/actualizó EN ESTA SESIÓN.

    En la primera carga de la sesión, si los archivos ya existen, los usa tal
    cual sin importar su antigüedad en disco.

    Sin parámetros.
    Retorna: None — puede disparar la corrida completa del ETL y un st.rerun().
    """
    # Caso 1: no hay datos en absoluto -> obligatorio correr el ETL, sin importar sesión
    if not _existen_archivos_gold():
        st.warning("⚠️ No se encontraron datos Gold. Ejecutando el pipeline ETL por primera vez...")
        _ejecutar_etl("Ejecutando main_etl.py")
        return  # nunca llega aquí por el st.rerun(), pero por claridad

    # Caso 2: primera vez que se revisa en ESTA sesión -> usa lo que haya, sin chequear antigüedad
    if "proxima_actualizacion" not in st.session_state:
        st.session_state["proxima_actualizacion"] = time.time() + CACHE_TTL_SEGUNDOS
        st.sidebar.caption("🟢 Datos cargados desde Gold (sesión nueva)")
        return

    # Caso 3: ya hubo al menos un chequeo en esta sesión -> comparar contra la marca guardada
    tiempo_restante = st.session_state["proxima_actualizacion"] - time.time()

    if tiempo_restante <= 0:
        st.info("🔄 Han pasado 30 minutos. Actualizando datos...")
        _ejecutar_etl("Ejecutando main_etl.py")
    else:
        st.sidebar.caption(f"🟢 Próxima actualización en {tiempo_restante / 60:.0f} min")


# ============================================================
# CARGA DE DATOS
# ============================================================

@st.cache_data(ttl=CACHE_TTL_SEGUNDOS, show_spinner="Cargando datos del Gold layer...")
def cargar_datos_gold() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Carga los tres datasets Gold: cuentas de ahorro, DPF y tarjetas de crédito.
    Sin parámetros — usa las rutas constantes definidas en el módulo.
    Retorna: tuple (cuentas_df, dpf_df, tc_df).
    """
    cuentas_df = pd.read_parquet(ARCHIVO_CUENTAS)
    dpf_df = pd.read_parquet(ARCHIVO_DPF)
    tc_df = pd.read_parquet(ARCHIVO_TC)
    return cuentas_df, dpf_df, tc_df