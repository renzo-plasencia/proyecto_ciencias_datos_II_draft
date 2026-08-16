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

log = logger.setup_log('etl_scotiabank_ahorros')

CONFIG = {
    "output_dir": Path(ROOT_DIR) / "output" / "silver",
    "parquet_path": Path(ROOT_DIR) / "output" / "silver" / "ahorros_scotiabank.parquet",
}

# 1. EXTRACCIÓN DE DATOS

def extraer_datos_ahorro_scotiabank(url: str, driver) -> dict:
    """Navega a la URL de Scotiabank, extrae el HTML renderizado y busca KPIs."""
    log.info(f"Navegando a: {url}")
    
    try:
        driver.get(url)
        time.sleep(3) # Pausa para carga inicial
        # Scroll para forzar la carga de los acordeones de preguntas frecuentes y beneficios
        scroll_suave(driver, paso=400, pausa=0.5) 
        html = driver.page_source
    except Exception as e:
        log.error(f"Error accediendo a la web {url}: {e}")
        return None
        
    nombre_extraido = url.split('/')[-1].replace('-', ' ').title()
        
    datos_cuenta = {
        "banco": "Scotiabank",
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
        texto_limpio = soup.get_text(separator=' ', strip=True)

        # --- A. Extracción de TREA ---
        # Buscamos patrones como "hasta 4.00% (TREA)" o "TREA de 0%"
        trea_match = re.search(r'(?:hasta)?\s*([\d\.]+)%\s*\(?TREA\)?|TREA.*?([\d\.]+)%', texto_limpio, re.IGNORECASE)
        if trea_match:
            valor_trea = trea_match.group(1) if trea_match.group(1) else trea_match.group(2)
            datos_cuenta["trea_soles"] = float(valor_trea)

        # --- B. Extracción de Mantenimiento y Condiciones ---
        if "sin mantenimiento" in texto_limpio.lower() or "sin costo de mantenimiento" in texto_limpio.lower():
            datos_cuenta["mantenimiento_mensual"] = 0.0
            datos_cuenta["requisito_mantenimiento_gratis"] = "Cero Mantenimiento siempre"
        else:
            # Buscamos costo específico (ej. S/ 8.00 para la Power si no cumples)
            mant_match = re.search(r'(?:costo será de|mantenimiento de|comisión.*?)\s*(?:S/|Soles)\s*([\d\.]+)', texto_limpio, re.IGNORECASE)
            if mant_match:
                datos_cuenta["mantenimiento_mensual"] = float(mant_match.group(1))
            
            # Buscamos condición (ej. desde S/1,500)
            req_match = re.search(r'(?:saldo promedio|manteniendo un saldo|desde)\s*(?:S/|Soles)\s*([\d\,\.]+)', texto_limpio, re.IGNORECASE)
            if req_match:
                datos_cuenta["requisito_mantenimiento_gratis"] = f"Saldo >= {req_match.group(1)}"

        # --- C. Extracción de Monto de Apertura ---
        if "sin monto mínimo de apertura" in texto_limpio.lower() or "no hay monto mínimo para abrir" in texto_limpio.lower():
            datos_cuenta["monto_minimo_apertura"] = 0.0
        else:
            apertura_match = re.search(r'(?:monto mínimo.*?es de|abrir.*?desde)\s*(?:S/|Soles)\s*([\d\,\.]+)', texto_limpio, re.IGNORECASE)
            if apertura_match:
                datos_cuenta["monto_minimo_apertura"] = float(apertura_match.group(1).replace(',', ''))
            
        # --- D. Retiros (Cajeros Propios) ---
        if "retiros ilimitados" in texto_limpio.lower() or "operaciones ilimitadas" in texto_limpio.lower():
            datos_cuenta["retiros_gratuitos_cajero_propio"] = "Ilimitados"
        else:
            cajero_match = re.search(r'(\d+)\s*retiros libres en cajeros', texto_limpio, re.IGNORECASE)
            if cajero_match:
                datos_cuenta["retiros_gratuitos_cajero_propio"] = f"{cajero_match.group(1)} retiros"

        # --- E. Retiros (Ventanilla) ---
        vent_match = re.search(r'(\d+)\s*retiro\s*y/o\s*transferencia', texto_limpio, re.IGNORECASE)
        if vent_match:
            datos_cuenta["retiros_gratuitos_ventanilla"] = f"{vent_match.group(1)} retiros"

    except Exception as e:
        log.error(f"Error parseando datos de {url}: {e}")
        
    return datos_cuenta

# 2. PIPELINE PRINCIPAL 
def run_pipeline() -> pd.DataFrame:
    log.info("Iniciando extracción Scotiabank Ahorros (Modo ONLINE)...")
    CONFIG["output_dir"].mkdir(parents=True, exist_ok=True)
    
    urls_ahorros_scotiabank = [
        "https://www.scotiabank.com.pe/Personas/Ahorros/Cuentas-Bancarias/cuenta-digital",
        "https://www.scotiabank.com.pe/Personas/Ahorros/Cuentas-Bancarias/cuenta-power"
    ]
    
    try:
        driver = setup_driver()
    except Exception as e:
        log.error(f"Error al iniciar el navegador: {e}")
        return pd.DataFrame()

    datos_completos = []
    
    for url in urls_ahorros_scotiabank:
        datos = extraer_datos_ahorro_scotiabank(url, driver)
        if datos:
            datos_completos.append(datos)
            
    df = pd.DataFrame(datos_completos)
    if df.empty: 
        log.warning("No se extrajeron datos de ahorros de Scotiabank.")
        return df

    # Limpieza estándar 
    df["banco"] = df["banco"].astype(str)
    
    cols_float = df.select_dtypes(include=['float64']).columns
    df[cols_float] = df[cols_float].apply(pd.to_numeric, downcast='float')

    log.info("Ejecutando validación de calidad (Pandera) para Cuentas de Ahorro Scotiabank...")
    try:
        df = esquema_ahorros.validate(df)
        log.info("✅ Validación de Pandera superada con éxito para Scotiabank Ahorros.")
    except Exception as exc:
        log.error(f"❌ Error de validación en Scotiabank Ahorros: {exc}")
        raise
        
    df.to_parquet(CONFIG["parquet_path"], index=False)
    log.info(f"💾 Datos guardados en Capa Silver: {CONFIG['parquet_path']}")
    
    return df

if __name__ == "__main__":
    df_ahorros = run_pipeline()
    if not df_ahorros.empty:
        print("\n=== MÓDULO SCOTIABANK AHORROS COMPLETADO ===")
        print(df_ahorros[['producto_nombre', 'trea_soles', 'mantenimiento_mensual', 'requisito_mantenimiento_gratis']].head())