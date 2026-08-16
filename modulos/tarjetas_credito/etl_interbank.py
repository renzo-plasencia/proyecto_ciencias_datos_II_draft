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

# CONFIGURACIÓN DE RUTAS Y MÓDULOS GLOBALES
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from utils import logger
from utils.browser import setup_driver
from utils.schemas import esquema_tarjetas 

log = logger.setup_log('etl_interbank')

CONFIG = {
    "urls_interbank": [
        "https://interbank.pe/tarjetas/tarjetas-credito/american-express-benefit?rfid=categoria:tarjetas:millas:american-express-blue",
        "https://interbank.pe/tarjetas/tarjetas-credito/american-express?fid=categoria:tarjetas:millas:american-express",
        "https://interbank.pe/tarjetas/tarjetas-credito/american-express-gold?rfid=categoria:tarjetas:millas:american-express-gold",
        "https://interbank.pe/tarjetas/tarjetas-credito/american-express-platinum?rfid=categoria:tarjetas:millas:american-express-platinum",
        "https://interbank.pe/tarjetas/tarjetas-credito/american-express-black?rfid=categoria:tarjetas:millas:american-express-black",
        "https://interbank.pe/tarjetas/tarjetas-credito/american-express-the-platinum-card?rfid=categoria:tarjetas:millas:the-platinum-card-american-express-de-interbank",
        "https://interbank.pe/tarjetas/tarjetas-credito/visa-clasica?rfid=categoria:tarjetas:millas:visa-clasica",
        "https://interbank.pe/tarjetas/tarjetas-credito/visa-oro?rfid=categoria:tarjetas:millas:visa-oro",
        "https://interbank.pe/tarjetas/tarjetas-credito/visa-platinum?rfid=categoria:tarjetas:millas:visa-platinum",
        "https://interbank.pe/tarjetas/tarjetas-credito/visa-signature?rfid=categoria:tarjetas:millas:visa-signature",
        "https://interbank.pe/tarjetas/tarjetas-credito/visa-infinite?rfid=categoria:tarjetas:millas:visa-infinite",
        "https://interbank.pe/tarjetas/tarjetas-credito/visa-premia?rfid=categoria:tarjetas:cupones:visa-premia",
        "https://interbank.pe/tarjetas/tarjetas-credito/visa-access?rfid=categoria:tarjetas:millas:visa-access"
    ],
    "output_dir": Path(ROOT_DIR) / "output" / "silver",
    "parquet_path": Path(ROOT_DIR) / "output" / "silver" / "tarjetas_interbank.parquet",
}

# 1. EXTRACCIÓN DE DATOS 
def extraer_datos_tarjeta(driver, url):
    log.info(f"Navegando a: {url}")
    driver.get(url)
    time.sleep(4) 
    
    tiempo_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    datos_tarjeta = {
        "banco": "Interbank",
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
        "fuente": "Interbank"
    }
    
    wait = WebDriverWait(driver, 7)
    
    try:
        nombre_ruta = url.split('/')[-1].split('?')[0]
        nombre_limpio = nombre_ruta.replace('-', ' ').title()
        datos_tarjeta["nombre_tarjeta"] = nombre_limpio
        datos_tarjeta["producto_nombre"] = nombre_limpio
        
        nombre_lower = nombre_limpio.lower()
        if "visa" in nombre_lower: datos_tarjeta["categoria"] = "Visa"
        elif "american express" in nombre_lower or "amex" in nombre_lower: datos_tarjeta["categoria"] = "American Express"

        def abrir_acordeon(texto_pestana):
            try:
                pestana = wait.until(EC.presence_of_element_located((By.XPATH, f"//*[normalize-space(text())='{texto_pestana}']")))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", pestana)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", pestana)
                time.sleep(1.5)
            except:
                pass

        abrir_acordeon("Resumen")
        abrir_acordeon("Requisitos")

        texto_pagina = driver.find_element(By.TAG_NAME, "body").text
        for linea in texto_pagina.split('\n'):
            linea_limpia = linea.lower().strip()
            
            if "membresía anual" in linea_limpia:
                if "gratis" in linea_limpia:
                    datos_tarjeta["membresia_anual_soles"] = 0.0
                else:
                    numeros = re.findall(r"s/\s*(\d+\.?\d*)", linea_limpia)
                    if numeros: datos_tarjeta["membresia_anual_soles"] = float(numeros[0])
            
            if "ingreso" in linea_limpia and ("mínimo" in linea_limpia or "minimo" in linea_limpia):
                ingreso = re.search(r"s/\s*([\d,]+)", linea_limpia)
                if ingreso: datos_tarjeta["ingreso_minimo_requerido"] = float(ingreso.group(1).replace(",", ""))
            
            millas = re.search(r"([\d.]+)\s+[Mm]illas?\s+por\s+cada", linea_limpia)
            if millas: datos_tarjeta["millas_por_dolar_consumo"] = float(millas.group(1))

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        beneficios_interbank = []
        
        titulos_beneficios = soup.find_all(['h1', 'h3'], class_=re.compile(r'g-sub-title'))
        for titulo in titulos_beneficios:
            texto = titulo.text.strip()
            if texto and texto not in beneficios_interbank:
                beneficios_interbank.append(texto)
                
        if beneficios_interbank:
            datos_tarjeta["beneficios_clave"] = ", ".join(beneficios_interbank[:3])
            datos_tarjeta["beneficio_principal"] = beneficios_interbank[0]
                    
    except Exception as e:
        log.error(f"Error procesando la tarjeta {url}: {e}")
        
    return datos_tarjeta

# 2. ENRIQUECIMIENTO BÁSICO
def enriquecer_interbank(df: pd.DataFrame, log) -> pd.DataFrame:
    df_enriched = df.copy()
    
    condiciones = [
        df_enriched['nombre_tarjeta'].str.contains('black|infinite|platinum card', case=False, na=False),
        df_enriched['nombre_tarjeta'].str.contains('platinum|signature', case=False, na=False),
        df_enriched['nombre_tarjeta'].str.contains('oro|gold|premia', case=False, na=False),
        df_enriched['nombre_tarjeta'].str.contains('clásica|clasica|blue|benefit|access', case=False, na=False)
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
    log.info("Iniciando extracción INTERBANK (Capa Silver)...")
    CONFIG["output_dir"].mkdir(parents=True, exist_ok=True)
    
    driver = setup_driver(headless=True)
    datos_completos = []
    
    try:
        for url in CONFIG["urls_interbank"]:
            datos = extraer_datos_tarjeta(driver, url)
            datos_completos.append(datos)
            time.sleep(1) 
    finally:
        log.info("Desvinculando navegador Interbank...")
        
    df = pd.DataFrame(datos_completos)
    if df.empty: return df

    df = enriquecer_interbank(df, log)

    # Forzar float64
    cols_float = df.select_dtypes(include=['float32', 'float64', 'int64', 'int32']).columns
    for col in cols_float:
        df[col] = pd.to_numeric(df[col], errors='coerce').astype('float64')

    log.info("Ejecutando validación de calidad (Pandera)...")
    try:
        df = esquema_tarjetas.validate(df)
        log.info("✅ Validación de Pandera superada con éxito para Interbank.")
    except Exception as exc:
        log.error(f"❌ Error de validación en Interbank: {exc}")
        raise
        
    df.to_parquet(CONFIG["parquet_path"], index=False)
    log.info(f"💾 Datos guardados en Capa Silver: {CONFIG['parquet_path']}")
    
    return df

if __name__ == "__main__":
    df_test = run_pipeline()
    if not df_test.empty:
        print("\n=== MÓDULO INTERBANK COMPLETADO ===")
        print(df_test[['nombre_tarjeta', 'membresia_anual_soles', 'beneficios_clave']].head())