import os
import sys
import time

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(ROOT_DIR)

from utils import logger
from utils.browser import launch_debug_chrome, close_debug_chrome

log = logger.setup_log('main_etl_orquestador')

# IMPORTACIÓN DINÁMICA DE MÓDULOS

# 1. Cuentas de Ahorro
modulos_ahorros = {}
try:
    from modulos.cuentas_ahorro.etl_banbif_ahorros import run_pipeline as run_ahorro_banbif
    modulos_ahorros['BanBif'] = run_ahorro_banbif
    
    from modulos.cuentas_ahorro.etl_bbva_ahorros import run_pipeline as run_ahorro_bbva
    modulos_ahorros['BBVA'] = run_ahorro_bbva
    
    from modulos.cuentas_ahorro.etl_bcp_ahorros import run_pipeline as run_ahorro_bcp
    modulos_ahorros['BCP'] = run_ahorro_bcp
    
    from modulos.cuentas_ahorro.etl_interbank_ahorros import run_pipeline as run_ahorro_ibk
    modulos_ahorros['Interbank'] = run_ahorro_ibk
    
    from modulos.cuentas_ahorro.etl_scotiabank_ahorros import run_pipeline as run_ahorro_scotia
    modulos_ahorros['Scotiabank'] = run_ahorro_scotia
except ImportError as e:
    log.warning(f"Falta algún módulo de Ahorros: {e}")

# 2. Depósitos a Plazo
modulos_plazos = {}
try:
    from modulos.depositos_plazo.etl_plazo_fijo import run_pipeline as run_plazo_fijo
    modulos_plazos['Consolidado_DPF'] = run_plazo_fijo
except ImportError as e:
    log.warning(f"Falta módulo de Depósitos a Plazo: {e}")

# 3. Tarjetas de Crédito
modulos_tarjetas = {}
try:
    from modulos.tarjetas_credito.etl_banbif import run_pipeline as run_tc_banbif
    modulos_tarjetas['BanBif'] = run_tc_banbif
    
    from modulos.tarjetas_credito.etl_bbva import run_pipeline as run_tc_bbva
    modulos_tarjetas['BBVA'] = run_tc_bbva
    
    from modulos.tarjetas_credito.etl_bcp import run_pipeline as run_tc_bcp
    modulos_tarjetas['BCP'] = run_tc_bcp
    
    from modulos.tarjetas_credito.etl_interbank import run_pipeline as run_tc_ibk
    modulos_tarjetas['Interbank'] = run_tc_ibk
    
    from modulos.tarjetas_credito.etl_scotiabank import run_pipeline as run_tc_scotia
    modulos_tarjetas['Scotiabank'] = run_tc_scotia
except ImportError as e:
    log.warning(f"Falta algún módulo de Tarjetas de Crédito: {e}")

# 4. Capa Gold (Consolidación)
try:
    from builder_gold import consolidar_capa_gold
except ImportError as e:
    log.warning(f"Falta módulo de Capa Gold: {e}")
    consolidar_capa_gold = None


# FUNCIÓN DE EJECUCIÓN POR BLOQUES
def ejecutar_bloque(nombre_bloque, diccionario_modulos):
    log.info(f"\n>>> INICIANDO BLOQUE: {nombre_bloque.upper()} <<<")
    if not diccionario_modulos:
        log.warning(f"No hay scripts cargados para el bloque {nombre_bloque}.")
        return

    for nombre_modulo, funcion_pipeline in diccionario_modulos.items():
        log.info(f"--- Extrayendo datos de {nombre_modulo} ---")
        try:
            df = funcion_pipeline()
            if df is not None and not df.empty:
                log.info(f"✔ Éxito en {nombre_modulo}: {len(df)} registros extraídos.")
            else:
                log.warning(f"⚠ {nombre_modulo} se ejecutó pero no devolvió datos.")
        except Exception as e:
            log.error(f"❌ Fallo crítico en {nombre_modulo}: {e}")

# FLUJO PRINCIPAL
def main():
    chrome_process = None
    try:
        log.info("="*60)
        log.info("🚀 INICIANDO PIPELINE PRINCIPAL (MAIN_ETL) 🚀")
        log.info("="*60)

        chrome_process = launch_debug_chrome(port=9222, log=log)
        start_time = time.time()
        
        # 1. Capa Silver: Ejecutar todas las extracciones
        ejecutar_bloque("Cuentas de Ahorro", modulos_ahorros)
        ejecutar_bloque("Tarjetas de Crédito", modulos_tarjetas)
        ejecutar_bloque("Depósitos a Plazo Fijo", modulos_plazos)
        
        # 2. Capa Gold: Consolidar la información extraída
        log.info("\n>>> INICIANDO BLOQUE: CONSOLIDACIÓN CAPA GOLD <<<")
        if consolidar_capa_gold:
            try:
                consolidar_capa_gold()
                log.info("✔ Éxito en la consolidación de la Capa Gold.")
            except Exception as e:
                log.error(f"❌ Fallo crítico en la consolidación Gold: {e}")
        else:
            log.warning("⚠ No se pudo ejecutar la Capa Gold (módulo no encontrado).")
        
        end_time = time.time()
        duracion = round((end_time - start_time) / 60, 2)
        
        log.info("="*60)
        log.info(f"🏁 ORQUESTACIÓN FINALIZADA EN {duracion} MINUTOS 🏁")
        log.info("="*60)
    finally:
        close_debug_chrome(chrome_process, log=log)
        
if __name__ == "__main__":
    main()