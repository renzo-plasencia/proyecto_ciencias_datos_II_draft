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
from utils.transformations import extraer_numero
from utils.browser import setup_driver, scroll_suave

log = logger.setup_log('etl_bbva_ahorros')

CONFIG = {
    "output_dir": Path(ROOT_DIR) / "output" / "silver",
    "parquet_path": Path(ROOT_DIR) / "output" / "silver" / "ahorros_bbva.parquet",
}

# 1. EXTRACCIÓN DE DATOS 

def extraer_datos_ahorro_bbva(url: str, driver) -> dict:
    """Navega a la URL de BBVA, extrae el HTML renderizado y busca KPIs."""
    log.info(f"Navegando a: {url}")
    
    try:
        driver.get(url)
        time.sleep(4) # Pausa un poco más larga por las animaciones de BBVA
        # El scroll suave forzará la carga de los acordeones de "Tasas" y "Comisiones"
        scroll_suave(driver, paso=400, pausa=0.5) 
        html = driver.page_source
    except Exception as e:
        log.error(f"Error accediendo a la web {url}: {e}")
        return None
        
    nombre_extraido = url.split('/')[-1].replace('.html', '').replace('-', ' ').title()
        
    datos_cuenta = {
        "banco": "BBVA",
        "producto_nombre": f"Cuenta {nombre_extraido}".strip(),
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
        # Obtenemos todo el texto limpio de la página para buscar con Regex
        texto_limpio = soup.get_text(separator=' ', strip=True)

        # --- A. Extracción de TREA ---
        # Busca patrones como "TREA 0%" o "TREA* Soles Mínima: 0,25%"
        trea_match = re.search(r'TREA(?:.*?Soles.*?Mínima:?\s*|\s*|\D*)([\d\,\.]+)%', texto_limpio, re.IGNORECASE)
        if trea_match:
            trea_str = trea_match.group(1).replace(',', '.')
            datos_cuenta["trea_soles"] = float(trea_str)

        # --- B. Extracción de Mantenimiento ---
        costo_base = re.search(r'Saldos menores.*?S/\s*([\d\.]+)', texto_limpio, re.IGNORECASE)
        if costo_base:
            datos_cuenta["mantenimiento_mensual"] = float(costo_base.group(1))
        
        # Evaluamos condiciones de gratuidad
        mant_cond = re.search(r'(?:si mantienes|saldo promedio.*?mínimo de)\s*(S/\s*[\d\,\.]+)', texto_limpio, re.IGNORECASE)
        if mant_cond:
            datos_cuenta["requisito_mantenimiento_gratis"] = f"Saldo >= {mant_cond.group(1)}"
        elif "no cobra mantenimiento" in texto_limpio.lower() or "sin costo de mantenimiento" in texto_limpio.lower():
            datos_cuenta["requisito_mantenimiento_gratis"] = "Cero Mantenimiento siempre"
            datos_cuenta["mantenimiento_mensual"] = 0.0

        # --- C. Extracción de Monto de Apertura ---
        apertura_match = re.search(r'Monto mínimo de apertura:\s*(S/\s*[\d\,\.]+)', texto_limpio, re.IGNORECASE)
        if apertura_match:
            saldo_str = apertura_match.group(1).replace('S/', '').replace(',', '').strip()
            datos_cuenta["monto_minimo_apertura"] = float(saldo_str)
            
        # --- D. Retiros ---
        if "retiros ilimitados y sin costo en cajeros" in texto_limpio.lower() or "ilimitada" in texto_limpio.lower():
             datos_cuenta["retiros_gratuitos_cajero_propio"] = "Ilimitados"
        else:
             retiros_match = re.search(r'(\d+)\s*retiros libres en cajeros', texto_limpio, re.IGNORECASE)
             if retiros_match:
                 datos_cuenta["retiros_gratuitos_cajero_propio"] = f"{retiros_match.group(1)} retiros"

    except Exception as e:
        log.error(f"Error parseando datos de {url}: {e}")
        
    return datos_cuenta

# 2. PIPELINE PRINCIPAL 
def run_pipeline() -> pd.DataFrame:
    log.info("Iniciando extracción BBVA Ahorros (Modo ONLINE)...")
    CONFIG["output_dir"].mkdir(parents=True, exist_ok=True)
    
    # URLs clave del BBVA
    urls_ahorros_bbva = [
        "https://www.bbva.pe/personas/productos/cuentas/ahorro/cuenta-digital.html",
        "https://www.bbva.pe/personas/productos/cuentas/ahorro/independencia.html",
        "https://www.bbva.pe/personas/productos/cuentas/ahorro/ganadora.html",
        "https://www.bbva.pe/personas/productos/cuentas/corriente/vip.html"
    ]
    
    try:
        driver = setup_driver()
    except Exception as e:
        log.error(f"Error al iniciar el navegador: {e}")
        return pd.DataFrame()

    datos_completos = []
    
    for url in urls_ahorros_bbva:
        datos = extraer_datos_ahorro_bbva(url, driver)
        if datos:
            datos_completos.append(datos)
            
    df = pd.DataFrame(datos_completos)
    if df.empty: 
        log.warning("No se extrajeron datos de ahorros del BBVA.")
        return df

    # Limpieza estándar 
    df["banco"] = df["banco"].astype(str)
    # Limpiamos nombre de la VIP para que no quede raro
    df["producto_nombre"] = df["producto_nombre"].str.replace("Cuenta Vip", "Cuenta VIP").str.strip()
    
    cols_float = df.select_dtypes(include=['float64']).columns
    df[cols_float] = df[cols_float].apply(pd.to_numeric, downcast='float')

    log.info("Ejecutando validación de calidad (Pandera) para Cuentas de Ahorro BBVA...")
    try:
        df = esquema_ahorros.validate(df)
        log.info("✅ Validación de Pandera superada con éxito para BBVA Ahorros.")
    except Exception as exc:
        log.error(f"❌ Error de validación en BBVA Ahorros: {exc}")
        raise
        
    df.to_parquet(CONFIG["parquet_path"], index=False)
    log.info(f"💾 Datos guardados en Capa Silver: {CONFIG['parquet_path']}")
    
    return df

if __name__ == "__main__":
    df_ahorros = run_pipeline()
    if not df_ahorros.empty:
        print("\n=== MÓDULO BBVA AHORROS COMPLETADO ===")
        print(df_ahorros[['producto_nombre', 'trea_soles', 'mantenimiento_mensual', 'requisito_mantenimiento_gratis']].head())