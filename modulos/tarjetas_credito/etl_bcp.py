import os
import sys
import json
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

# Importamos nuestras utilidades centralizadas
from utils import logger
from utils.browser import setup_driver
# Validación estricta activada
from utils.schemas import esquema_tarjetas

# Inicializamos el logger con el nombre del banco
log = logger.setup_log('etl_bcp')

# CONFIGURACIÓN ESPECÍFICA DE ESTE MÓDULO

CONFIG = {
    "urls_bcp": [
        "https://www.viabcp.com/tarjetas/american-express-clasica?pcid=viabcp:tarjetas-tarjetas-credito:amex-clasica-latam-pass:masivo:producto-detalle",
        "https://www.viabcp.com/tarjetas/american-express-gold?pcid=viabcp:tarjetas-tarjetas-credito:amex-oro-latam-pass:masivo:producto-detalle",
        "https://www.viabcp.com/tarjetas/american-express-platinum?pcid=viabcp:tarjetas-tarjetas-credito:amex-platinum-latam-pass:masivo:producto-detalle",
        "https://www.viabcp.com/tarjetas/american-express-black?pcid=viabcp:tarjetas-tarjetas-credito:amex-black-latam-pass:masivo:producto-detalle",
        "https://www.viabcp.com/tarjetas/visa-latampass-clasica?pcid=viabcp:tarjetas-tarjetas-credito:visa-clasica-latam-pass:masivo:producto-detalle",
        "https://www.viabcp.com/tarjetas/visa-latampass-oro?pcid=viabcp:tarjetas-tarjetas-credito:visa-oro-latam-pass:masivo:producto-detalle",
        "https://www.viabcp.com/tarjetas/visa-latampass-platinum?pcid=viabcp:tarjetas-tarjetas-credito:visa-platinum-latam-pass:masivo:producto-detalle",
        "https://www.viabcp.com/tarjetas/visa-latampass-signature?pcid=viabcp:tarjetas-tarjetas-credito:visa-signature-latam-pass:masivo:producto-detalle",
        "https://www.viabcp.com/tarjetas/sapphire?pcid=viabcp:tarjetas-tarjetas-credito:visa-infinite-sapphire-latam-p:masivo:producto-detalle",
        "https://www.viabcp.com/tarjetas/visa-platinum-qore?pcid=viabcp:tarjetas-tarjetas-credito:visa-platinum-qore:masivo:producto-detalle",
        "https://www.viabcp.com/tarjetas/credito-visa-clasica?pcid=viabcp:tarjetas-tarjetas-credito:visa-clasica:masivo:producto-detalle",
        "https://www.viabcp.com/tarjetas/visa-signature-qore?pcid=viabcp:tarjetas-tarjetas-credito:visa-signature-qore:masivo:producto-detalle",
        "https://www.viabcp.com/tarjetas/visa-infinite-qore?pcid=viabcp:tarjetas-tarjetas-credito:visa-infinite-qore:masivo:producto-detalle",
        "https://www.viabcp.com/tarjetas/credito-visa-light?pcid=viabcp:tarjetas-tarjetas-credito:visa-light:masivo:producto-detalle"
    ],
    "output_dir": Path(ROOT_DIR) / "output" / "silver",
    "parquet_path": Path(ROOT_DIR) / "output" / "silver" / "tarjetas_bcp.parquet",
}

# ============================================================
# 1. EXTRACCIÓN DE DATOS (La receta única del BCP)
# ============================================================
def extraer_datos_tarjeta(driver, url):
    """Extrae las columnas base de una tarjeta BCP."""
    log.info(f"Navegando a: {url}")
    driver.get(url)
    time.sleep(3)
    
    tiempo_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Diccionario alineado con el esquema estandarizado
    datos_tarjeta = {
        "banco": "BCP",
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
        "fuente": "BCP"
    }
    
    wait = WebDriverWait(driver, 10)
    
    try:
        # A. Extraer nombre y marca
        try:
            titulo = wait.until(EC.presence_of_element_located((By.XPATH, "//h1 | //h2[contains(@class, 'title') or contains(@class, 'heading')]")))
            nombre_limpio = titulo.text.strip()
            datos_tarjeta["nombre_tarjeta"] = nombre_limpio
            datos_tarjeta["producto_nombre"] = nombre_limpio
            
            nombre_lower = nombre_limpio.lower()
            if "visa" in nombre_lower: datos_tarjeta["categoria"] = "Visa"
            elif "amex" in nombre_lower or "american express" in nombre_lower: datos_tarjeta["categoria"] = "American Express"
        except:
            log.warning("No se capturó el nombre.")

        # B. Clic en "Tasas y Tarifas" 
        try:
            pestaña_tasas = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Tasas y Tarifas') or contains(text(), 'Tasas y tarifas')]")))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", pestaña_tasas)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", pestaña_tasas)
            time.sleep(1.5)
            
            texto_tasas = driver.find_element(By.TAG_NAME, "body").text
            for linea in texto_tasas.split('\n'):
                linea_limpia = linea.lower().strip()
                if "membresía anual" in linea_limpia and "s/" in linea_limpia:
                    numeros = re.findall(r"s/\s*(\d+\.?\d*)", linea_limpia)
                    if numeros:
                        datos_tarjeta["membresia_anual_soles"] = float(numeros[0])
        except:
            log.warning("No se encontró la pestaña 'Tasas y Tarifas'.")

        # C. Clic en "Requisitos" (Para Ingreso Mínimo)
        try:
            pestaña_requisitos = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Requisitos')]")))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", pestaña_requisitos)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", pestaña_requisitos)
            time.sleep(1.5)
            
            texto_requisitos = driver.find_element(By.TAG_NAME, "body").text
            for linea in texto_requisitos.split('\n'):
                linea_limpia = linea.lower().strip()
                if "ingreso" in linea_limpia and "mínimo" in linea_limpia and "s/" in linea_limpia:
                    ingreso = re.search(r"s/\s*([\d,]+)", linea_limpia)
                    if ingreso:
                        datos_tarjeta["ingreso_minimo_requerido"] = float(ingreso.group(1).replace(",", ""))
        except:
            log.warning("No se encontró la pestaña 'Requisitos'.")

        # D. Clic en "Beneficios" y extracción con BeautifulSoup
        try:
            pestaña_beneficios = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Beneficios')]")))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", pestaña_beneficios)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", pestaña_beneficios)
            time.sleep(1.5)
            
            # Parseamos el HTML con BeautifulSoup
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            beneficios_bcp = []
            tab_beneficios = soup.find('div', attrs={'data-titulo': 'Beneficios'})
            
            if tab_beneficios:
                titulos_h3 = tab_beneficios.find_all('h3')
                for h3 in titulos_h3:
                    texto_beneficio = h3.text.strip()
                    if "Afíliate" not in texto_beneficio and "Conoce otras" not in texto_beneficio and "Beneficios" not in texto_beneficio:
                        beneficios_bcp.append(texto_beneficio)
                        
            if beneficios_bcp:
                datos_tarjeta["beneficios_clave"] = ", ".join(beneficios_bcp[:3])
                datos_tarjeta["beneficio_principal"] = beneficios_bcp[0]
        except:
            log.warning("No se encontró la pestaña 'Beneficios'.")
                    
    except Exception as e:
        log.error(f"Error procesando la tarjeta: {e}")
        
    return datos_tarjeta

# 2. ENRIQUECIMIENTO BÁSICO PARA ADAPTAR AL ESQUEMA

def enriquecer_bcp(df: pd.DataFrame, log) -> pd.DataFrame:
    """Aplica la lógica financiera y adapta las columnas para que pasen el esquema."""
    df_enriched = df.copy()
    
    # 1. Segmentación basada en nombre 
    condiciones = [
        df_enriched['nombre_tarjeta'].str.contains('black|infinite|signature', case=False, na=False),
        df_enriched['nombre_tarjeta'].str.contains('platinum', case=False, na=False),
        df_enriched['nombre_tarjeta'].str.contains('oro|gold', case=False, na=False),
        df_enriched['nombre_tarjeta'].str.contains('clásica|clasica|light|cero', case=False, na=False)
    ]
    elecciones = ['Elite', 'Premium', 'Intermedio', 'Básico'] 
    df_enriched['segmento_gasto'] = np.select(condiciones, elecciones, default='Básico')

    # --- IMPUTACIÓN DE INGRESO MÍNIMO ---
    estimaciones_ingreso = {
        'Básico': 1500.0,      
        'Intermedio': 3000.0,
        'Premium': 7000.0,
        'Elite': 12000.0
    }
    
    df_enriched['ingreso_minimo_requerido'] = df_enriched.apply(
        lambda row: estimaciones_ingreso.get(row['segmento_gasto'], 1500.0) if row['ingreso_minimo_requerido'] == 0.0 else row['ingreso_minimo_requerido'],
        axis=1
    )

    # 2. Cálculos financieros 
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
    log.info("Iniciando extracción BCP (Capa Silver)...")
    CONFIG["output_dir"].mkdir(parents=True, exist_ok=True)
    
    driver = setup_driver(headless=True)
    datos_completos = []
    
    try:
        for url in CONFIG["urls_bcp"]:
            datos = extraer_datos_tarjeta(driver, url)
            datos_completos.append(datos)
            time.sleep(1) 
    finally:
        log.info("Desvinculando navegador BCP...")
        # driver.quit() # COMENTADO PARA RESPETAR EL MODO ESCUCHA DEL NAVEGADOR
        
    df = pd.DataFrame(datos_completos)
    if df.empty:
        log.error("❌ No se extrajeron datos.")
        return df

    # Enriquecemos la tabla
    df = enriquecer_bcp(df, log)

    # ==========================================================
    # CORRECCIÓN DE TIPO DE DATO FLOAT64 PARA PANDERA
    # ==========================================================
    log.info("Optimizando uso de memoria y tipos de datos...")
    
    # Aseguramos que todas las columnas numéricas relevantes sean float64 explícitamente
    cols_float = df.select_dtypes(include=['float32', 'float64']).columns
    for col in cols_float:
        df[col] = df[col].astype('float64')
        
    # El esquema pide segmento_gasto como string, no category
    df['segmento_gasto'] = df['segmento_gasto'].astype(str)

    # Validación estricta Pandera
    log.info("Ejecutando validación de calidad (Pandera)...")
    try:
        df = esquema_tarjetas.validate(df)
        log.info("✅ Validación de Pandera superada con éxito para BCP.")
    except Exception as exc:
        log.error(f"❌ Error de validación en BCP: {exc}")
        raise
        
    # Persistencia
    df.to_parquet(CONFIG["parquet_path"], index=False)
    log.info(f"💾 Datos guardados en Capa Silver: {CONFIG['parquet_path']}")
    
    return df

if __name__ == "__main__":
    df_test = run_pipeline()
    if not df_test.empty:
        print("\n=== MÓDULO BCP COMPLETADO ===")
        print(df_test[['nombre_tarjeta', 'segmento_gasto', 'membresia_anual_soles', 'beneficios_clave']].head())