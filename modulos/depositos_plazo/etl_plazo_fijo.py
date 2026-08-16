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
from utils.browser import setup_driver, scroll_suave

log = logger.setup_log('etl_plazo_fijo')

CONFIG = {
    "output_dir": Path(ROOT_DIR) / "output" / "silver",
    "parquet_path": Path(ROOT_DIR) / "output" / "silver" / "plazo_fijo_bancos.parquet",
    # Ruta dinámica apuntando a la subcarpeta BanBif que creaste
    "html_dir": Path(__file__).parent / "BanBif" 
}

# Diccionario maestro con la configuración de cada banco
FUENTES_DPF = {
    "BCP": {
        "modo": "online",
        "url": "https://www.viabcp.com/inversiones/deposito-plazo-fijo/pago-de-intereses-al-vencimiento"
    },
    "BBVA": {
        "modo": "online",
        "url": "https://www.bbva.pe/personas/productos/inversiones/depositos/deposito-plazo.html"
    },
    "Interbank": {
        "modo": "online",
        "url": "https://interbank.pe/cuentas/cuentas-ahorro/deposito-a-plazo-fijo"
    },
    "Scotiabank": {
        "modo": "online",
        "url": "https://www.scotiabank.com.pe/Personas/Depositos-e-inversion/Productos/deposito-a-plazo"
    },
    "BanBif": {
        "modo": "offline",
        "archivo_local": "BANBIF_PLAZOFIJO.html", # Asegúrate de que el archivo se llame exactamente así
        "url": "https://www.banbif.com.pe/personas/cuentas/mayor-rentabilidad/deposito-plazo-fijo"
    }
}

# FUNCIONES DE EXTRACCIÓN Y PARSEO
def extraer_datos(html: str, banco: str, url_origen: str) -> dict:
    """Aplica expresiones regulares al HTML según el banco para extraer KPIs."""
    datos = {
        "banco": banco,
        "producto": "Depósito a Plazo Fijo",
        "moneda": "Soles", 
        "monto_minimo_apertura": 0.0,
        "trea_maxima_promocional": 0.0,
        "fecha_scraping": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "url_origen": url_origen
    }
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        texto_limpio = soup.get_text(separator=' ', strip=True).replace('\n', ' ')

        # Lógica de Regex personalizada por banco
        if banco == "BCP":
            trea_match = re.search(r'TREA.*?([\d\.]+)%', texto_limpio, re.IGNORECASE)
            monto_match = re.search(r'Desde\s*(?:S/|S/.)\s*([\d\,\.]+)', texto_limpio, re.IGNORECASE)
            
        elif banco == "BBVA":
            trea_match = re.search(r'(?:Hasta\s*)?([\d\.]+)%\s*TREA\s*soles', texto_limpio, re.IGNORECASE)
            monto_match = re.search(r'Desde\s*(?:S/|S/.)\s*([\d\,\.]+)', texto_limpio, re.IGNORECASE)
            
        elif banco == "Interbank":
            trea_match = re.search(r'hasta\s*([\d\.]+)%', texto_limpio, re.IGNORECASE)
            monto_match = re.search(r'Monto de apertura:?\s*(?:S/|S/.)\s*([\d\,\.]+)', texto_limpio, re.IGNORECASE)
            
        elif banco == "Scotiabank":
            trea_match = re.search(r'hasta\s*([\d\.]+)%\s*TREA', texto_limpio, re.IGNORECASE)
            monto_match = re.search(r'(?:desde\s*)?(?:S/|S/.)\s*([\d\,\.]+)', texto_limpio, re.IGNORECASE)
            
        elif banco == "BanBif":
            trea_match = re.search(r'TREA\s*(?:de|hasta)?\s*([\d\.]+)%', texto_limpio, re.IGNORECASE)
            monto_match = re.search(r'(?:S/|S/.)\s*([\d\,\.]+)\s*o\s*\$', texto_limpio, re.IGNORECASE)
            if not monto_match: 
                monto_match = re.search(r'desde\s*(?:S/|S/.)\s*([\d\,\.]+)', texto_limpio, re.IGNORECASE)

        if trea_match:
            datos["trea_maxima_promocional"] = float(trea_match.group(1))
        if monto_match:
            datos["monto_minimo_apertura"] = float(monto_match.group(1).replace(',', ''))

    except Exception as e:
        log.error(f"Error parseando datos de {banco}: {e}")
        
    return datos


# PIPELINE HÍBRIDO PRINCIPAL

def run_pipeline() -> pd.DataFrame:
    log.info("Iniciando extracción Híbrida de Depósitos a Plazo Fijo...")
    CONFIG["output_dir"].mkdir(parents=True, exist_ok=True)
    
    driver = None
    datos_completos = []
    
    for banco, config in FUENTES_DPF.items():
        html_content = ""
        
        # MODO ONLINE
        if config["modo"] == "online":
            log.info(f"[{banco}] Extrayendo en modo ONLINE: {config['url']}")
            try:
                if not driver:
                    driver = setup_driver()
                driver.get(config["url"])
                time.sleep(4) 
                scroll_suave(driver, paso=400, pausa=0.5)
                html_content = driver.page_source
            except Exception as e:
                log.error(f"[{banco}] Fallo en la extracción online: {e}")
                continue
                
        # MODO OFFLINE
        elif config["modo"] == "offline":
            log.info(f"[{banco}] Extrayendo en modo OFFLINE desde archivo local.")
            ruta_local = CONFIG["html_dir"] / config["archivo_local"]
            try:
                with open(ruta_local, 'r', encoding='utf-8') as f:
                    html_content = f.read()
            except Exception as e:
                log.error(f"[{banco}] No se pudo leer el archivo local {ruta_local}: {e}")
                continue
        
        # PROCESAMIENTO COMÚN
        if html_content:
            datos_banco = extraer_datos(html_content, banco, config["url"])
            if datos_banco:
                datos_completos.append(datos_banco)
                
    if driver:
        driver.quit()
            
    df = pd.DataFrame(datos_completos)
    if df.empty: 
        log.warning("No se extrajeron datos de Plazo Fijo.")
        return df

    # Limpieza estándar
    cols_float = df.select_dtypes(include=['float64']).columns
    df[cols_float] = df[cols_float].apply(pd.to_numeric, downcast='float')

    df.to_parquet(CONFIG["parquet_path"], index=False)
    log.info(f"💾 Datos DPF guardados en Capa Silver: {CONFIG['parquet_path']}")
    
    return df

if __name__ == "__main__":
    df_dpf = run_pipeline()
    if not df_dpf.empty:
        print("\n=== MÓDULO DEPÓSITOS A PLAZO FIJO (HÍBRIDO) COMPLETADO ===")
        print(df_dpf[['banco', 'trea_maxima_promocional', 'monto_minimo_apertura']])