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
from utils.browser import setup_driver, scroll_suave  # <-- Importamos tus utilidades web

log = logger.setup_log('etl_bcp_ahorros')

CONFIG = {
    "output_dir": Path(ROOT_DIR) / "output" / "silver",
    "parquet_path": Path(ROOT_DIR) / "output" / "silver" / "ahorros_bcp.parquet",
}

# 1. EXTRACCIÓN DE DATOS 

def extraer_datos_ahorro_online(url: str, driver) -> dict:
    """Navega a la URL de BCP, escrollea y extrae las condiciones financieras."""
    log.info(f"Navegando a: {url}")
    
    try:
        driver.get(url)
        time.sleep(3) # Pausa para que el DOM inicial cargue
        # El scroll suave es CLAVE para que los bloques ocultos o lazy-loading aparezcan
        scroll_suave(driver, paso=500, pausa=0.5) 
        html = driver.page_source
    except Exception as e:
        log.error(f"Error accediendo a la web {url}: {e}")
        return None
        
    # Extraer un nombre amigable desde la URL (ej. cuenta-digital-bcp -> Cuenta Digital)
    nombre_extraido = url.split('/')[-1].replace('-bcp', '').replace('-', ' ').title()
        
    # Diccionario base 
    datos_cuenta = {
        "banco": "BCP",
        "producto_nombre": f"Cuenta {nombre_extraido}".strip(),
        "trea_soles": 0.0,
        "monto_minimo_apertura": 0.0,
        "mantenimiento_mensual": 0.0,
        "requisito_mantenimiento_gratis": "Sin condiciones especificadas",
        "retiros_gratuitos_cajero_propio": "Consultar web",
        "retiros_gratuitos_ventanilla": "Consultar web",
        "fecha_scraping": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "url_origen": url
    }
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Función auxiliar para encontrar el texto de la lista debajo de un título <h3>
        def buscar_texto_lista(patron_titulo):
            h3 = soup.find('h3', string=re.compile(patron_titulo, re.IGNORECASE))
            if h3:
                ul = h3.find_next_sibling('ul')
                if ul:
                    return " ".join([li.get_text(" ", strip=True) for li in ul.find_all('li')])
            return ""

        # --- A. Extracción de TREA ---
        texto_trea = buscar_texto_lista(r'TREA')
        trea_match = extraer_numero(texto_trea, r'Soles:[^\d]*([\d\.]+)%')
        if trea_match is not None:
            datos_cuenta["trea_soles"] = trea_match
        else:
            # Plan B: Buscar en el texto legal del footer
            footer_trea = re.search(r'TREA referencial de ([\d\.]+)%', soup.get_text(separator=' '))
            if footer_trea:
                datos_cuenta["trea_soles"] = float(footer_trea.group(1))

        # --- B. Extracción de Mantenimiento ---
        texto_mant = buscar_texto_lista(r'Costo de mantenimiento')
        if texto_mant:
            if "sin costo" in texto_mant.lower() or "no se cobra" in texto_mant.lower():
                datos_cuenta["mantenimiento_mensual"] = 0.0
                datos_cuenta["requisito_mantenimiento_gratis"] = "No aplica (Cero Mantenimiento)"
                
                condicion_gratis = re.search(r'(Para cuentas con saldos.*|Para saldos.*)', texto_mant)
                if condicion_gratis:
                    datos_cuenta["requisito_mantenimiento_gratis"] = condicion_gratis.group(1)
            else:
                costo_mant = extraer_numero(texto_mant, r'S/\s*([\d\.]+)')
                datos_cuenta["mantenimiento_mensual"] = costo_mant if costo_mant else 0.0

        # --- C. Extracción de Retiros y Ventanilla ---
        texto_ventanilla = buscar_texto_lista(r'Ventanillas BCP')
        if texto_ventanilla:
            datos_cuenta["retiros_gratuitos_ventanilla"] = texto_ventanilla

        texto_cajeros = buscar_texto_lista(r'Cajeros')
        if texto_cajeros:
            cajero_propio = re.search(r'Cajeros BCP:(.*?)(?:Cajeros de otras|$)', texto_cajeros)
            if cajero_propio:
                datos_cuenta["retiros_gratuitos_cajero_propio"] = cajero_propio.group(1).strip()
            else:
                datos_cuenta["retiros_gratuitos_cajero_propio"] = texto_cajeros

        # --- D. Saldo mínimo apertura (Equilibrio) ---
        texto_saldo = buscar_texto_lista(r'Saldo mínimo')
        saldo_apertura = extraer_numero(texto_saldo, r'Soles:\s*S/\s*([\d,\.]+)')
        if saldo_apertura:
            datos_cuenta["monto_minimo_apertura"] = saldo_apertura

    except Exception as e:
        log.error(f"Error extrayendo datos de {url}: {e}")
        
    return datos_cuenta

# 2. PIPELINE PRINCIPAL 

def run_pipeline() -> pd.DataFrame:
    log.info("Iniciando extracción BCP Ahorros (Modo ONLINE)...")
    CONFIG["output_dir"].mkdir(parents=True, exist_ok=True)
    
    # URLs de los productos a procesar
    urls_ahorros_bcp = [
        "https://www.viabcp.com/cuentas/cuenta-ahorro/cuenta-digital-bcp",
        "https://www.viabcp.com/cuentas/cuenta-ahorro/cuenta-premio-bcp",
        "https://www.viabcp.com/cuentas/cuenta-ahorro/cuenta-ilimitada-bcp"
    ]
    
    # Iniciar Selenium con tu navegador local
    try:
        driver = setup_driver()
    except Exception as e:
        log.error(f"Error al iniciar el navegador: {e}")
        return pd.DataFrame()

    datos_completos = []
    
    for url in urls_ahorros_bcp:
        datos = extraer_datos_ahorro_online(url, driver)
        if datos:
            datos_completos.append(datos)
            
    df = pd.DataFrame(datos_completos)
    if df.empty: 
        log.warning("No se extrajeron datos de ahorros.")
        return df

    # Limpieza estándar y downcasting 
    df["banco"] = df["banco"].astype(str)
    
    # Limpiamos si se genera un "Cuenta Cuenta", para dejarlo solo como "Cuenta Digital"
    df["producto_nombre"] = df["producto_nombre"].str.replace("Cuenta Cuenta", "Cuenta").str.strip()
    
    cols_float = df.select_dtypes(include=['float64']).columns
    df[cols_float] = df[cols_float].apply(pd.to_numeric, downcast='float')

    log.info("Ejecutando validación de calidad (Pandera) para Cuentas de Ahorro...")
    try:
        df = esquema_ahorros.validate(df)
        log.info("✅ Validación de Pandera superada con éxito para BCP Ahorros.")
    except Exception as exc:
        log.error(f"❌ Error de validación en BCP Ahorros: {exc}")
        raise
        
    df.to_parquet(CONFIG["parquet_path"], index=False)
    log.info(f"💾 Datos guardados en Capa Silver: {CONFIG['parquet_path']}")
    
    return df

if __name__ == "__main__":
    # ¡Recuerda abrir Chrome en modo debugging antes de ejecutar!
    # Windows+R -> chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\selenum\ChromeProfile"
    df_ahorros = run_pipeline()
    if not df_ahorros.empty:
        print("\n=== MÓDULO BCP AHORROS COMPLETADO ===")
        print(df_ahorros[['producto_nombre', 'trea_soles', 'mantenimiento_mensual']].head())