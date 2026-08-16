import os
import sys
import re
import time
from datetime import datetime
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup

# CONFIGURACIÓN DE RUTAS Y MÓDULOS GLOBALES
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from utils import logger
from utils.schemas import esquema_ahorros
from utils.browser import setup_driver, scroll_suave

log = logger.setup_log('etl_interbank_ahorros')

CONFIG = {
    "output_dir": Path(ROOT_DIR) / "output" / "silver",
    "parquet_path": Path(ROOT_DIR) / "output" / "silver" / "ahorros_interbank.parquet",
}

# 1. EXTRACCIÓN DE DATOS (SCRAPING ONLINE INTERBANK)
def extraer_datos_ahorro_interbank(url: str, driver) -> dict:
    """Navega a la URL de Interbank, extrae el HTML renderizado y busca KPIs."""
    log.info(f"Navegando a: {url}")
    
    try:
        driver.get(url)
        time.sleep(3) # Pausa para carga inicial
        # Scroll para forzar la carga de los acordeones de tarifas y beneficios
        scroll_suave(driver, paso=400, pausa=0.5) 
        html = driver.page_source
    except Exception as e:
        log.error(f"Error accediendo a la web {url}: {e}")
        return None
        
    nombre_extraido = url.split('/')[-1].replace('cuenta-', 'Cuenta ').replace('-', ' ').title()
    # Limpiamos parámetros de URL si los hay (ej. ?tabs=conoce-mas)
    nombre_extraido = nombre_extraido.split('?')[0].strip()
        
    datos_cuenta = {
        "banco": "Interbank",
        "producto_nombre": nombre_extraido,
        "trea_soles": 0.0,
        "monto_minimo_apertura": 0.0,
        "mantenimiento_mensual": 0.0,
        "requisito_mantenimiento_gratis": "Sin condiciones",
        "retiros_gratuitos_cajero_propio": "Consultar web",
        "retiros_gratuitos_ventanilla": "Consultar web",
        "fecha_scraping": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "url_origen": url
    }
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        # Todo el texto limpio para la búsqueda por Regex
        texto_limpio = soup.get_text(separator=' ', strip=True)

        # --- A. Extracción de TREA ---
        trea_match = re.search(r'(?:TREA(?:.*?máxima|.*?referencial:?|.*?de)?|hasta)\s*([\d\.]+)%\s*(?:TREA|en soles)?', texto_limpio, re.IGNORECASE)
        if trea_match:
            datos_cuenta["trea_soles"] = float(trea_match.group(1))

        # --- B. Extracción de Mantenimiento y Condiciones ---
        if "cero costo de mantenimiento" in texto_limpio.lower() or "sin costo de mantenimiento" in texto_limpio.lower():
            datos_cuenta["mantenimiento_mensual"] = 0.0
            datos_cuenta["requisito_mantenimiento_gratis"] = "Cero Mantenimiento siempre"
        else:
            # Buscamos costo de mantenimiento
            mant_match = re.search(r'(?:mantenimiento|Sujetos a cobro).*?S/\s*([\d\.]+)', texto_limpio, re.IGNORECASE)
            if mant_match:
                datos_cuenta["mantenimiento_mensual"] = float(mant_match.group(1))
            
            # Buscamos la condición para exonerar
            req_match = re.search(r'saldo promedio(?:.*?)(?:S/|Soles)\s*([\d\,\.]+)', texto_limpio, re.IGNORECASE)
            if req_match:
                datos_cuenta["requisito_mantenimiento_gratis"] = f"Saldo >= {req_match.group(1)}"

        # --- C. Extracción de Monto de Apertura ---
        apertura_match = re.search(r'(?:Monto de apertura|desde)\s*:?\s*(?:S/|Soles)\s*([\d\,\.]+)', texto_limpio, re.IGNORECASE)
        if apertura_match:
            saldo_str = apertura_match.group(1).replace(',', '')
            datos_cuenta["monto_minimo_apertura"] = float(saldo_str)
            
        # --- D. Retiros (Cajeros Global Net) ---
        cajero_match = re.search(r'Global Net.*?(?:\.|$)', texto_limpio, re.IGNORECASE)
        if cajero_match:
            fragmento_cajero = cajero_match.group(0).lower()
            if "ilimitados" in fragmento_cajero:
                datos_cuenta["retiros_gratuitos_cajero_propio"] = "Ilimitados"
            else:
                ret_match = re.search(r'(\d+)\s*retiros', fragmento_cajero)
                if ret_match:
                    datos_cuenta["retiros_gratuitos_cajero_propio"] = f"{ret_match.group(1)} retiros"

    except Exception as e:
        log.error(f"Error parseando datos de {url}: {e}")
        
    return datos_cuenta

# 2. PIPELINE PRINCIPAL 
def run_pipeline() -> pd.DataFrame:
    log.info("Iniciando extracción Interbank Ahorros (Modo ONLINE)...")
    CONFIG["output_dir"].mkdir(parents=True, exist_ok=True)
    
    # URLs clave del escuadrón Interbank
    urls_ahorros_interbank = [
        "https://interbank.pe/cuentas/cuentas-ahorro/cuenta-simple?tabs=conoce-mas",
        "https://interbank.pe/cuentas/cuentas-ahorro/cuenta-millonaria",
        "https://interbank.pe/cuentas/cuentas-ahorro/cuenta-super-tasa?tabs=tab-como-incremento-mi-ahorro"
    ]
    
    try:
        driver = setup_driver()
    except Exception as e:
        log.error(f"Error al iniciar el navegador: {e}")
        return pd.DataFrame()

    datos_completos = []
    
    for url in urls_ahorros_interbank:
        datos = extraer_datos_ahorro_interbank(url, driver)
        if datos:
            datos_completos.append(datos)
            
    df = pd.DataFrame(datos_completos)
    if df.empty: 
        log.warning("No se extrajeron datos de ahorros de Interbank.")
        return df

    # Limpieza estándar 
    df["banco"] = df["banco"].astype(str)
    
    cols_float = df.select_dtypes(include=['float64']).columns
    df[cols_float] = df[cols_float].apply(pd.to_numeric, downcast='float')

    log.info("Ejecutando validación de calidad (Pandera) para Cuentas de Ahorro Interbank...")
    try:
        df = esquema_ahorros.validate(df)
        log.info("✅ Validación de Pandera superada con éxito para Interbank Ahorros.")
    except Exception as exc:
        log.error(f"❌ Error de validación en Interbank Ahorros: {exc}")
        raise
        
    df.to_parquet(CONFIG["parquet_path"], index=False)
    log.info(f"💾 Datos guardados en Capa Silver: {CONFIG['parquet_path']}")
    
    return df

if __name__ == "__main__":
    df_ahorros = run_pipeline()
    if not df_ahorros.empty:
        print("\n=== MÓDULO INTERBANK AHORROS COMPLETADO ===")
        print(df_ahorros[['producto_nombre', 'trea_soles', 'mantenimiento_mensual', 'requisito_mantenimiento_gratis']].head())