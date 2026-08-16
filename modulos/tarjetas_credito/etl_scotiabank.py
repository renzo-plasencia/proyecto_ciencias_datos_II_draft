import os
import sys
import time
import re
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ============================================================
# CONFIGURACIÓN DE RUTAS Y MÓDULOS GLOBALES
# ============================================================
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from utils import logger
from utils.browser import setup_driver
from utils.schemas import esquema_tarjetas 

log = logger.setup_log('etl_scotiabank')

CONFIG = {
    "urls_scotiabank": [
        "https://www.scotiabank.com.pe/Personas/tarjetas/tarjeta-credito-visa/visa-smart",
        "https://www.scotiabank.com.pe/Personas/tarjetas/tarjeta-credito-visa/visa-clasica-sin-membresia",
        "https://www.scotiabank.com.pe/Personas/tarjetas/tarjeta-credito-visa/visa-oro",
        "https://www.scotiabank.com.pe/Personas/tarjetas/tarjeta-credito-visa/visa-platinum",
        "https://www.scotiabank.com.pe/beyond/tarjetas/tarjetas-de-credito/visa-infinite",
        "https://www.scotiabank.com.pe/Personas/tarjetas/tarjeta-credito-visa/visa-clasica",
        "https://www.scotiabank.com.pe/Personas/tarjetas/tarjeta-credito-visa/aadvantage-visa-gold",
        "https://www.scotiabank.com.pe/Personas/tarjetas/tarjeta-credito-visa/aadvantage-visa-platinum",
        "https://www.scotiabank.com.pe/Personas/tarjetas/tarjeta-credito-visa/aadvantage-visa-signature",
        "https://www.scotiabank.com.pe/Personas/tarjetas/tarjeta-credito-visa/aadvantage-visa-infinite",
        "https://www.scotiabank.com.pe/premium/tarjetas/tarjetas-de-credito/visa-signature",
        "https://www.scotiabank.com.pe/Personas/tarjetas/tarjeta-credito-visa/aadvantage-visa-silver"
    ],
    "output_dir": Path(ROOT_DIR) / "output" / "silver",
    "parquet_path": Path(ROOT_DIR) / "output" / "silver" / "tarjetas_scotiabank.parquet",
}

# 1. EXTRACCIÓN DE DATOS
def extraer_datos_tarjeta(driver, url):
    log.info(f"Navegando a: {url}")
    driver.get(url)
    time.sleep(4) 
    
    tiempo_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Diccionario adaptado al esquema de Pandera
    datos_tarjeta = {
        "banco": "Scotiabank",
        "producto_nombre": "Desconocido",
        "nombre_tarjeta": "Desconocido",
        "categoria": "Desconocido",
        "tcea_maxima": None,
        "membresia_anual_soles": 0.0,
        "requisito_exoneracion_membresia": None,
        "beneficio_principal": None,
        "millas_por_dolar_consumo": 1.0, 
        "bono_bienvenida_millas": 0.0,
        "ingreso_minimo_requerido": 0.0, 
        "beneficios_clave": "Consultar detalles en web",
        "url_origen": url,
        "url_detalle": url,
        "fecha_scraping": tiempo_actual,
        "fecha_extraccion": tiempo_actual,
        "fuente": "Scotiabank"
    }
    
    try:
        # A. Nombre y categoría
        nombre_ruta = url.split('/')[-1].split('?')[0].replace('-', ' ').title()
        datos_tarjeta["nombre_tarjeta"] = nombre_ruta
        datos_tarjeta["producto_nombre"] = nombre_ruta
        nombre_lower = nombre_ruta.lower()
        if "visa" in nombre_lower: datos_tarjeta["categoria"] = "Visa"
        elif "mastercard" in nombre_lower or "smart" in nombre_lower: datos_tarjeta["categoria"] = "Mastercard"

        # B. Forzar la apertura de TODAS las pestañas
        pestañas = driver.find_elements(By.CSS_SELECTOR, "li.tab-link")
        for pestaña in pestañas:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", pestaña)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", pestaña)
                time.sleep(0.5)
            except:
                pass

        # C. Parseo del HTML
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        # D. Extraer Beneficios 
        beneficios = []
        botones_acordeon = soup.find_all('button', class_=re.compile(r'desplegable'))
        for btn in botones_acordeon:
            texto = btn.text.strip()
            if texto and "documentos" not in texto.lower() and "generales" not in texto.lower():
                if texto not in beneficios:
                    beneficios.append(texto)
                    
        if beneficios:
            datos_tarjeta["beneficios_clave"] = ", ".join(beneficios[:3])
            datos_tarjeta["beneficio_principal"] = beneficios[0]

        # E. Extraer Ingresos y Membresía del texto de los paneles con control de errores
        texto_pagina = soup.get_text(separator='\n').lower()
        for linea in texto_pagina.split('\n'):
            linea_limpia = linea.strip()
            
            # Buscar Ingreso Mínimo 
            if "ingreso" in linea_limpia and "mínimo" in linea_limpia and "s/" in linea_limpia:
                ingreso = re.search(r's/\s*([\d,\.]+)', linea_limpia)
                if ingreso:
                    # Limpiamos el texto para evitar que un punto final rompa la conversión a float
                    val_str = ingreso.group(1).replace(',', '').strip('.')
                    if val_str:
                        try:
                            datos_tarjeta["ingreso_minimo_requerido"] = float(val_str)
                        except ValueError:
                            pass
            
            # Buscar Membresía
            if "membresía" in linea_limpia and "s/" in linea_limpia and "meta" not in linea_limpia and "exoneración" not in linea_limpia:
                membresia = re.search(r's/\s*([\d,\.]+)', linea_limpia)
                if membresia:
                    val_str = membresia.group(1).replace(',', '').strip('.')
                    if val_str:
                        try:
                            valor = float(val_str)
                            if valor < 1000: 
                                datos_tarjeta["membresia_anual_soles"] = valor
                        except ValueError:
                            pass
                        
    except Exception as e:
        log.error(f"Error procesando la tarjeta {url}: {e}")
        
    return datos_tarjeta

# 2. ENRIQUECIMIENTO BÁSICO
def enriquecer_scotiabank(df: pd.DataFrame, log) -> pd.DataFrame:
    df_enriched = df.copy()
    
    condiciones = [
        df_enriched['nombre_tarjeta'].str.contains('black|infinite|beyond', case=False, na=False),
        df_enriched['nombre_tarjeta'].str.contains('platinum|signature', case=False, na=False),
        df_enriched['nombre_tarjeta'].str.contains('oro|gold', case=False, na=False),
        df_enriched['nombre_tarjeta'].str.contains('clásica|clasica|smart|puntos|silver', case=False, na=False)
    ]
    elecciones = ['Elite', 'Premium', 'Intermedio', 'Básico'] 
    df_enriched['segmento_gasto'] = np.select(condiciones, elecciones, default='Básico')

    estimaciones_ingreso = {'Básico': 1500.0, 'Intermedio': 3000.0, 'Premium': 7000.0, 'Elite': 12000.0}
    df_enriched['ingreso_minimo_requerido'] = df_enriched.apply(
        lambda row: estimaciones_ingreso.get(row['segmento_gasto'], 1500.0) if row['ingreso_minimo_requerido'] == 0.0 else row['ingreso_minimo_requerido'],
        axis=1
    )

    df_enriched["gasto_mensual_estimado_soles"] = df_enriched['segmento_gasto'].map({'Básico': 800.0, 'Intermedio': 2500.0, 'Premium': 6000.0, 'Elite': 12000.0})
    df_enriched["gasto_anual_estimado_soles"] = df_enriched["gasto_mensual_estimado_soles"] * 12
    
    df_enriched["valor_milla_soles"] = 0.03
    tasa_millas = df_enriched["millas_por_dolar_consumo"].fillna(1.0)
    
    df_enriched["millas_anuales_generadas"] = ((df_enriched["gasto_anual_estimado_soles"] / 3.75) * tasa_millas).round(0)
    df_enriched["valor_millas_anual_soles"] = (df_enriched["millas_anuales_generadas"] * df_enriched["valor_milla_soles"]).round(2)
    df_enriched["valor_bono_bienvenida_soles"] = (df_enriched["bono_bienvenida_millas"] * df_enriched["valor_milla_soles"]).round(2)
    
    df_enriched["valor_neto_primer_anio_soles"] = (df_enriched["valor_millas_anual_soles"] + df_enriched["valor_bono_bienvenida_soles"] - df_enriched["membresia_anual_soles"]).round(2)
    df_enriched["valor_neto_anual_recurrente_soles"] = (df_enriched["valor_millas_anual_soles"] - df_enriched["membresia_anual_soles"]).round(2)
    
    return df_enriched

# 3. PIPELINE PRINCIPAL 

def run_pipeline() -> pd.DataFrame:
    log.info("Iniciando extracción SCOTIABANK (Capa Silver)...")
    CONFIG["output_dir"].mkdir(parents=True, exist_ok=True)
    
    driver = setup_driver(headless=True)
    datos_completos = []
    
    try:
        for url in CONFIG["urls_scotiabank"]:
            datos = extraer_datos_tarjeta(driver, url)
            datos_completos.append(datos)
            time.sleep(1) 
    finally:
        log.info("Desvinculando navegador Scotiabank...")
        
    df = pd.DataFrame(datos_completos)
    if df.empty: return df

    df = enriquecer_scotiabank(df, log)

    # Convertir explícitamente a float64 para Pandera
    cols_float = df.select_dtypes(include=['float32', 'float64', 'int64', 'int32']).columns
    for col in cols_float:
        df[col] = pd.to_numeric(df[col], errors='coerce').astype('float64')

    log.info("Ejecutando validación de calidad (Pandera)...")
    try:
        df = esquema_tarjetas.validate(df)
        log.info("✅ Validación de Pandera superada con éxito para Scotiabank.")
    except Exception as exc:
        log.error(f"❌ Error de validación en Scotiabank: {exc}")
        raise
        
    df.to_parquet(CONFIG["parquet_path"], index=False)
    log.info(f"💾 Datos guardados en Capa Silver: {CONFIG['parquet_path']}")
    
    return df

if __name__ == "__main__":
    df_test = run_pipeline()
    if not df_test.empty:
        print("\n=== MÓDULO SCOTIABANK COMPLETADO ===")
        print(df_test[['nombre_tarjeta', 'ingreso_minimo_requerido', 'beneficios_clave']].head())