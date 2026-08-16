import os
import sys
import re
from datetime import datetime
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup

# CONFIGURACIÓN DE RUTAS Y MÓDULOS GLOBALES
# ROOT_DIR apunta a: C:\Users\jeanp\Downloads\Proyecto_Final_Lenguaje_Ciencia_Datos
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from utils import logger
from utils.schemas import esquema_ahorros

log = logger.setup_log('etl_banbif_ahorros_offline')

CONFIG = {
    "output_dir": Path(ROOT_DIR) / "output" / "silver",
    "parquet_path": Path(ROOT_DIR) / "output" / "silver" / "ahorros_banbif.parquet",
    # Ruta dinámica a tu carpeta actual: modulos/cuentas_ahorro/banbif_html
    "html_dir": Path(__file__).parent / "banbif_html" 
}

# Diccionario que vincula el archivo local con su URL de origen para el DataFrame
ARCHIVOS_LOCALES = {
    "GranCuentaAhorro.html": "https://www.banbif.com.pe/personas/cuentas/cuenta-ahorro/gran-cuenta-ahorro",
    "CuentaAhorro.html": "https://www.banbif.com.pe/personas/cuentas/cuenta-ahorro/cuenta-ahorro",
    "CuentaAhorroDigital.html": "https://www.banbif.com.pe/personas/cuentas/cuenta-ahorro/digital",
    "CuentaAhorroConveniente.html": "https://www.banbif.com.pe/personas/cuentas/cuenta-ahorro/conveniente",
    "CuentaAhorroGenial.html": "https://www.banbif.com.pe/personas/cuentas/cuenta-ahorro/genial"
}

# 1. EXTRACCIÓN DE DATOS (SCRAPING OFFLINE BANBIF)
def extraer_datos_ahorro_banbif_offline(archivo_html: str, url_origen: str) -> dict:
    """Lee un archivo HTML local y extrae los KPIs."""
    ruta_completa = CONFIG["html_dir"] / archivo_html
    log.info(f"Procesando archivo local: {archivo_html}")
    
    try:
        with open(ruta_completa, 'r', encoding='utf-8') as f:
            html = f.read()
    except Exception as e:
        log.error(f"Error leyendo el archivo local {archivo_html}. Asegúrate de que exista en la ruta correcta. Error: {e}")
        return None
        
    nombre_extraido = url_origen.split('/')[-1].replace('-', ' ').title()
    if nombre_extraido.lower() == "cuenta ahorro":
        nombre_extraido = "Cuenta De Ahorro Clasica"
        
    datos_cuenta = {
        "banco": "BanBif",
        "producto_nombre": f"Cuenta {nombre_extraido}",
        "trea_soles": 0.0,
        "monto_minimo_apertura": 0.0,
        "mantenimiento_mensual": 0.0,
        "requisito_mantenimiento_gratis": "Sin condiciones",
        "retiros_gratuitos_cajero_propio": "Consultar web",
        "retiros_gratuitos_ventanilla": "Consultar web",
        "fecha_scraping": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "url_origen": url_origen
    }
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        texto_limpio = soup.get_text(separator=' ', strip=True)

        # --- A. Extracción de TREA ---
        trea_match = re.search(r'(?:TREA.*?|tasa.*?|hasta)\s*([\d\.]+)%\s*(?:TREA)?', texto_limpio, re.IGNORECASE)
        if trea_match:
            datos_cuenta["trea_soles"] = float(trea_match.group(1))

        # --- B. Extracción de Mantenimiento y Condiciones ---
        if "sin costo por mantenimiento" in texto_limpio.lower() or "sin costo de mantenimiento" in texto_limpio.lower():
            datos_cuenta["mantenimiento_mensual"] = 0.0
            req_match = re.search(r'saldo promedio mensual de\s*(?:S/|Soles)\s*([\d\,\.]+)', texto_limpio, re.IGNORECASE)
            if req_match:
                datos_cuenta["requisito_mantenimiento_gratis"] = f"Saldo >= S/ {req_match.group(1)}"
            else:
                datos_cuenta["requisito_mantenimiento_gratis"] = "Cero Mantenimiento siempre"
                
        elif "sin mantenimiento de cuenta a partir de" in texto_limpio.lower():
            req_match = re.search(r'a partir de\s*(?:S/|Soles)\s*([\d\,\.]+)', texto_limpio, re.IGNORECASE)
            if req_match:
                datos_cuenta["requisito_mantenimiento_gratis"] = f"Saldo >= S/ {req_match.group(1)}"
                datos_cuenta["mantenimiento_mensual"] = -1.0 

        # --- C. Extracción de Monto de Apertura ---
        if "sin monto mínimo de apertura" in texto_limpio.lower() or "desde s/0" in texto_limpio.lower():
            datos_cuenta["monto_minimo_apertura"] = 0.0
        else:
            apertura_match = re.search(r'monto mínimo(?: de apertura)?:?\s*(?:S/|Soles)\s*([\d\,\.]+)', texto_limpio, re.IGNORECASE)
            if apertura_match:
                datos_cuenta["monto_minimo_apertura"] = float(apertura_match.group(1).replace(',', ''))

        # --- D. Retiros (Cajeros Propios y Globalnet) ---
        if "retiros ilimitados" in texto_limpio.lower() or "retiros sin costo en cajeros" in texto_limpio.lower():
            datos_cuenta["retiros_gratuitos_cajero_propio"] = "Ilimitados (BanBif y GlobalNet)"

        # --- E. Retiros (Ventanilla) ---
        if "depósitos y retiros sin costo" in texto_limpio.lower() or "sin costo en ventanillas" in texto_limpio.lower() or "retiros ilimitados en ventanillas" in texto_limpio.lower():
            datos_cuenta["retiros_gratuitos_ventanilla"] = "Ilimitados"

    except Exception as e:
        log.error(f"Error parseando datos de {archivo_html}: {e}")
        
    return datos_cuenta
# 2. PIPELINE PRINCIPAL 
def run_pipeline() -> pd.DataFrame:
    log.info("Iniciando extracción BanBif Ahorros (Modo OFFLINE)...")
    CONFIG["output_dir"].mkdir(parents=True, exist_ok=True)
    
    # Validar que el directorio exista
    if not CONFIG["html_dir"].exists():
        log.error(f"El directorio de HTML no existe: {CONFIG['html_dir']}. Por favor verifica el nombre.")
        return pd.DataFrame()

    datos_completos = []
    
    for archivo, url in ARCHIVOS_LOCALES.items():
        datos = extraer_datos_ahorro_banbif_offline(archivo, url)
        if datos:
            datos_completos.append(datos)
            
    df = pd.DataFrame(datos_completos)
    if df.empty: 
        log.warning("No se extrajeron datos de ahorros de BanBif.")
        return df

    # Limpieza estándar 
    df["banco"] = df["banco"].astype(str)
    
    cols_float = df.select_dtypes(include=['float64']).columns
    df[cols_float] = df[cols_float].apply(pd.to_numeric, downcast='float')

    log.info("Ejecutando validación de calidad (Pandera) para Cuentas de Ahorro BanBif...")
    try:
        df = esquema_ahorros.validate(df)
        log.info("✅ Validación de Pandera superada con éxito para BanBif Ahorros.")
    except Exception as exc:
        log.error(f"❌ Error de validación en BanBif Ahorros: {exc}")
        raise
        
    df.to_parquet(CONFIG["parquet_path"], index=False)
    log.info(f"💾 Datos guardados en Capa Silver: {CONFIG['parquet_path']}")
    
    return df

if __name__ == "__main__":
    df_ahorros = run_pipeline()
    if not df_ahorros.empty:
        print("\n=== MÓDULO BANBIF AHORROS (OFFLINE) COMPLETADO ===")
        print(df_ahorros[['producto_nombre', 'trea_soles', 'monto_minimo_apertura']].head(5))