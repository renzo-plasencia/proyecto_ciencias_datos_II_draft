import os
import sys
import re
from datetime import datetime
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup

# CONFIGURACIÓN DE RUTAS Y MÓDULOS GLOBALES
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from utils import logger
from utils.schemas import esquema_tarjetas

log = logger.setup_log('etl_banbif')

CONFIG = {
    "output_dir": Path(ROOT_DIR) / "output" / "silver",
    "parquet_path": Path(ROOT_DIR) / "output" / "silver" / "tc_banbif.parquet",
    "html_dir": Path(__file__).parent / "BanBif_HTML" 
}

# Nombres exactos de los archivos HTML presentes en tu estructura
ARCHIVOS_LOCALES = {
    "Visa Clasica BanBif.html": "https://www.banbif.com.pe/personas/tarjetas/tarjetas-credito/clasica",
    "Visa ORO - Gold.html": "https://www.banbif.com.pe/personas/tarjetas/tarjetas-credito/oro",
    "Mastercard Platinum.html": "https://www.banbif.com.pe/personas/tarjetas/tarjetas-credito/platinum",
    "Visa Signature.html": "https://www.banbif.com.pe/personas/tarjetas/tarjetas-credito/signature",
    "Visa Infinite.html": "https://www.banbif.com.pe/personas/tarjetas/tarjetas-credito/infinite",
    "Visa Cero Membresia.html": "https://www.banbif.com.pe/personas/tarjetas/tarjetas-credito/cero-membresia",
    "Crédito Más Efectivo.html": "https://www.banbif.com.pe/personas/tarjetas/tarjetas-credito/efectivo"
}

# 1. EXTRACCIÓN DE DATOS (SCRAPING OFFLINE BANBIF TC)

def extraer_datos_tc_banbif_offline(archivo_html: str, url_origen: str) -> dict:
    """Lee un archivo HTML local de Tarjetas de Crédito y extrae los KPIs."""
    ruta_completa = CONFIG["html_dir"] / archivo_html
    log.info(f"Procesando archivo local: {archivo_html}")
    
    try:
        with open(ruta_completa, 'r', encoding='utf-8') as f:
            html = f.read()
    except Exception as e:
        log.error(f"Error leyendo el archivo local {archivo_html}: {e}")
        return None
        
    nombre_tarjeta_limpio = archivo_html.replace('.html', '').replace('_', ' ')
    tiempo_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    datos_tc = {
        "banco": "BanBif",
        "producto_nombre": f"Tarjeta {nombre_tarjeta_limpio}",
        "nombre_tarjeta": f"Tarjeta {nombre_tarjeta_limpio}",
        "categoria": "Mastercard" if "Mastercard" in archivo_html else "Visa",
        "tcea_maxima": 0.0,
        "membresia_anual_soles": 0.0,
        "requisito_exoneracion_membresia": "Consultar web",
        "beneficio_principal": "Puntos BanBif",
        "beneficios_clave": "Puntos BanBif",
        "ingreso_minimo_requerido": 1500.0,
        "millas_por_dolar_consumo": 1.0,
        "bono_bienvenida_millas": 0.0,
        "segmento_gasto": "Básico",
        "gasto_mensual_estimado_soles": 800.0,
        "gasto_anual_estimado_soles": 9600.0,
        "valor_milla_soles": 0.03,
        "millas_anuales_generadas": 0.0,
        "valor_millas_anual_soles": 0.0,
        "valor_bono_bienvenida_soles": 0.0,
        "valor_neto_primer_anio_soles": 0.0,
        "valor_neto_anual_recurrente_soles": 0.0,
        "fecha_scraping": tiempo_actual,
        "fecha_extraccion": tiempo_actual,
        "url_origen": url_origen,
        "url_detalle": url_origen,
        "fuente": "BanBif"
    }
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        texto_limpio = soup.get_text(separator=' ', strip=True)

        # --- Extracción de TCEA ---
        tcea_match = re.search(r'(?:TCEA.*?|TCEA máxima.*?|hasta)\s*([\d\.]+)%', texto_limpio, re.IGNORECASE)
        if tcea_match:
            datos_tc["tcea_maxima"] = float(tcea_match.group(1))

        # --- Extracción de Membresía ---
        membresia_match = re.search(r'Membresía.*?(?:S/|Soles)\s*([\d\,\.]+)', texto_limpio, re.IGNORECASE)
        if membresia_match:
            datos_tc["membresia_anual_soles"] = float(membresia_match.group(1).replace(',', ''))

        # --- Extracción de Condiciones ---
        if "sin costo de membresía" in texto_limpio.lower() or "membresía gratis" in texto_limpio.lower() or "cero membresía" in texto_limpio.lower():
            datos_tc["membresia_anual_soles"] = 0.0
            datos_tc["requisito_exoneracion_membresia"] = "Cero Membresía siempre"
        elif "consumo mínimo" in texto_limpio.lower():
            req_match = re.search(r'consumo mínimo(?: de)?\s*(?:S/|Soles)\s*([\d\,\.]+)', texto_limpio, re.IGNORECASE)
            if req_match:
                datos_tc["requisito_exoneracion_membresia"] = f"Consumo >= S/ {req_match.group(1)} mensual"

    except Exception as e:
        log.error(f"Error parseando datos de {archivo_html}: {e}")
        
    return datos_tc

# ============================================================
# 2. PIPELINE PRINCIPAL 
# ============================================================
def run_pipeline() -> pd.DataFrame:
    log.info("Iniciando extracción Tarjetas de Crédito BanBif (Modo OFFLINE)...")
    CONFIG["output_dir"].mkdir(parents=True, exist_ok=True)
    
    if not CONFIG["html_dir"].exists():
        log.error(f"El directorio de HTML no existe: {CONFIG['html_dir']}")
        return pd.DataFrame()

    datos_completos = []
    
    for archivo, url in ARCHIVOS_LOCALES.items():
        if (CONFIG["html_dir"] / archivo).exists():
            datos = extraer_datos_tc_banbif_offline(archivo, url)
            if datos:
                datos_completos.append(datos)
        else:
            log.warning(f"Archivo {archivo} no encontrado en la carpeta BanBif_HTML. Omitiendo.")
            
    df = pd.DataFrame(datos_completos)
    if df.empty: 
        log.warning("No se extrajeron datos de Tarjetas de Crédito de BanBif.")
        return df

    log.info("Enriqueciendo datos y calculando KPIs...")
    promedio_neto = df['membresia_anual_soles'].mean() if 'membresia_anual_soles' in df.columns else 0.0
    log.info(f"Enriquecimiento completado. Valor promedio neto 1er año: S/ {promedio_neto:.2f}")

    # Forzar explícitamente float64 para cumplir con el esquema de Pandera
    cols_float = df.select_dtypes(include=['float32', 'float64', 'int64', 'int32']).columns
    for col in cols_float:
        df[col] = pd.to_numeric(df[col], errors='coerce').astype('float64')

    log.info("Ejecutando validación de calidad (Pandera)...")
    try:
        df = esquema_tarjetas.validate(df)
        log.info("✅ Validación de Pandera superada con éxito para BanBif TC.")
    except Exception as exc:
        log.error(f"❌ Error de validación en Banbif: {exc}")
        raise
        
    df.to_parquet(CONFIG["parquet_path"], index=False)
    log.info(f"💾 Datos guardados en Capa Silver: {CONFIG['parquet_path']}")
    
    return df

if __name__ == "__main__":
    df_tc = run_pipeline()
    if not df_tc.empty:
        print("\n=== MÓDULO BANBIF TARJETAS DE CRÉDITO (OFFLINE) COMPLETADO ===")
        print(df_tc[['producto_nombre', 'tcea_maxima', 'membresia_anual_soles']].head(5))