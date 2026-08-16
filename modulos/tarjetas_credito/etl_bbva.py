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

log = logger.setup_log('etl_bbva')

CONFIG = {
    "urls_bbva": [
        "https://www.bbva.pe/personas/productos/tarjetas/credito/visa-bfree-puntos-vida.html",
        "https://www.bbva.pe/personas/productos/tarjetas/credito/visa-cero.html",
        "https://www.bbva.pe/personas/productos/tarjetas/credito/tarjeta-basica.html",
        "https://www.bbva.pe/personas/productos/tarjetas/credito/tarjeta-platinum.html",
        "https://www.bbva.pe/personas/productos/tarjetas/credito/visa-signature-puntos-vida.html",
        "https://www.bbva.pe/personas/productos/tarjetas/credito/visa-infinite-puntos.html",
        "https://www.bbva.pe/personas/productos/tarjetas/credito/mastercard-bfree-puntos-vida.html",
        "https://www.bbva.pe/personas/productos/tarjetas/credito/mastercard-black-puntos-vida.html"
    ],
    "output_dir": Path(ROOT_DIR) / "output" / "silver",
    "parquet_path": Path(ROOT_DIR) / "output" / "silver" / "tarjetas_bbva.parquet",
}

# 1. EXTRACCIÓN DE DATOS 
def extraer_datos_tarjeta(driver, url):
    log.info(f"Navegando a: {url}")
    driver.get(url)
    time.sleep(4) 
    
    tiempo_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    datos_tarjeta = {
        "banco": "BBVA",
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
        "beneficios_clave": "Consultar detalles", 
        "url_origen": url,
        "url_detalle": url,
        "fecha_scraping": tiempo_actual,
        "fecha_extraccion": tiempo_actual,
        "fuente": "BBVA"
    }
    
    wait = WebDriverWait(driver, 5)
    
    try:
        nombre_ruta = url.split('/')[-1].replace('.html', '')
        nombre_limpio = nombre_ruta.replace('-', ' ').title()
        datos_tarjeta["nombre_tarjeta"] = nombre_limpio
        datos_tarjeta["producto_nombre"] = nombre_limpio
        
        nombre_lower = nombre_limpio.lower()
        if "visa" in nombre_lower: datos_tarjeta["categoria"] = "Visa"
        elif "mastercard" in nombre_lower: datos_tarjeta["categoria"] = "Mastercard"

        def clickear_pestana(texto):
            try:
                pestana = wait.until(EC.element_to_be_clickable((By.XPATH, f"//*[normalize-space(text())='{texto}']")))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", pestana)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", pestana)
                time.sleep(1.5)
            except:
                pass

        clickear_pestana("Costos y comisiones")
        clickear_pestana("Requisitos")
        clickear_pestana("Beneficios")

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        ingreso_title = soup.find('h3', string=re.compile(r'Ingreso m[íi]nimo', re.IGNORECASE))
        if ingreso_title:
            bloque_texto = ingreso_title.find_next_sibling('div', class_='productdescription__mod__bodycopy')
            if bloque_texto:
                match = re.search(r'[S/\$]*\s*([\d,\.]+)', bloque_texto.text)
                if match:
                    datos_tarjeta["ingreso_minimo_requerido"] = float(match.group(1).replace(",", ""))

        for p in soup.find_all('p'):
            if 'Membresía anual' in p.text:
                match = re.search(r'Membresía anual[:\s]*[S/\$]*\s*([\d,\.]+)', p.text, re.IGNORECASE)
                if match:
                    datos_tarjeta["membresia_anual_soles"] = float(match.group(1).replace(",", ""))
                    break

        beneficios = []
        titulos_h3 = soup.find_all('h3', class_='productdescription__mod__normalhead')
        for h3 in titulos_h3:
            texto_h3 = h3.text.strip()
            if texto_h3 not in ["Ingreso mínimo", "Condiciones", "Documentación", "Tasa Efectiva Anual (TEA)", "Tasa de Costo Efectiva Anual (TCEA)", "Otros Gastos y Comisiones", "Requisitos", "Beneficios"]:
                beneficios.append(texto_h3)
                
        if beneficios:
            datos_tarjeta["beneficios_clave"] = ", ".join(beneficios[:3])
            datos_tarjeta["beneficio_principal"] = beneficios[0]
                    
    except Exception as e:
        log.error(f"Error procesando la tarjeta {url}: {e}")
        
    return datos_tarjeta

# 2. ENRIQUECIMIENTO BÁSICO
def enriquecer_bbva(df: pd.DataFrame, log) -> pd.DataFrame:
    df_enriched = df.copy()
    
    condiciones = [
        df_enriched['nombre_tarjeta'].str.contains('black|infinite', case=False, na=False),
        df_enriched['nombre_tarjeta'].str.contains('platinum|signature', case=False, na=False),
        df_enriched['nombre_tarjeta'].str.contains('oro|gold', case=False, na=False),
        df_enriched['nombre_tarjeta'].str.contains('bfree|cero|basica', case=False, na=False)
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
    log.info("Iniciando extracción BBVA (Capa Silver)...")
    CONFIG["output_dir"].mkdir(parents=True, exist_ok=True)
    
    driver = setup_driver(headless=True)
    datos_completos = []
    
    try:
        for url in CONFIG["urls_bbva"]:
            datos = extraer_datos_tarjeta(driver, url)
            datos_completos.append(datos)
            time.sleep(1) 
    finally:
        log.info("Desvinculando navegador BBVA...")

    df = pd.DataFrame(datos_completos)
    if df.empty: return df

    df = enriquecer_bbva(df, log)

    # Forzar float64
    cols_float = df.select_dtypes(include=['float32', 'float64', 'int64', 'int32']).columns
    for col in cols_float:
        df[col] = pd.to_numeric(df[col], errors='coerce').astype('float64')

    log.info("Ejecutando validación de calidad (Pandera)...")
    try:
        df = esquema_tarjetas.validate(df)
        log.info("✅ Validación de Pandera superada con éxito para BBVA.")
    except Exception as exc:
        log.error(f"❌ Error de validación en BBVA: {exc}")
        raise

    df.to_parquet(CONFIG["parquet_path"], index=False)
    log.info(f"💾 Datos guardados en Capa Silver: {CONFIG['parquet_path']}")
    
    return df

if __name__ == "__main__":
    df_test = run_pipeline()
    if not df_test.empty:
        print("\n=== MÓDULO BBVA COMPLETADO ===")
        print(df_test[['nombre_tarjeta', 'membresia_anual_soles', 'ingreso_minimo_requerido', 'beneficios_clave']].head())