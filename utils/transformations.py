import pandas as pd
import numpy as np
import re
import logging
from typing import Optional, Tuple



# 1. EXTRACCIÓN DE NÚMEROS (Regex)

def extraer_numero(texto: str, patron: str) -> Optional[float]:
    """Extrae un número de un texto usando expresiones regulares y limpia símbolos."""
    if not texto: 
        return None
    m = re.search(patron, texto, flags=re.IGNORECASE)
    if not m: 
        return None
    try: 
        return float(m.group(1).replace(",", "").replace("%", ""))
    except (ValueError, IndexError): 
        return None

# 2. LIMPIEZA ESTÁNDAR

def limpiar_datos_tarjetas(df: pd.DataFrame, log: logging.Logger) -> pd.DataFrame:
    """Aplica la limpieza inicial de nulos, duplicados y formatos de texto."""
    df_clean = df.copy()
    
    # Limpieza de strings
    for col in ["nombre_tarjeta", "categoria", "url_detalle"]:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].astype(str).str.strip().replace("nan", None)
            
    # Eliminar duplicados
    if "nombre_tarjeta" in df_clean.columns and "fecha_extraccion" in df_clean.columns:
        df_clean = df_clean.drop_duplicates(subset=["nombre_tarjeta", "fecha_extraccion"])
        
    # Convertir a numérico y rellenar nulos (¡AQUÍ ESTÁ LA NUEVA LÍNEA!)
    num_cols = ["membresia_anual_soles", "millas_por_dolar_consumo", "bono_bienvenida_millas", "ingreso_minimo_requerido"]
    for col in num_cols:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce").fillna(0.0)
    
    # Eliminar filas sin nombre de tarjeta
    if "nombre_tarjeta" in df_clean.columns:
        df_clean = df_clean[df_clean["nombre_tarjeta"].notna() & (df_clean["nombre_tarjeta"] != "")]
        
    log.info(f"🧹 Limpieza aplicada. Quedan {len(df_clean)} filas.")
    return df_clean.reset_index(drop=True)

# 3. ENRIQUECIMIENTO Y CÁLCULOS FINANCIEROS

def enriquecer_tarjetas(df: pd.DataFrame, log: logging.Logger) -> pd.DataFrame:
    """Calcula segmentos de gasto, valor de millas y valores netos anuales."""
    df_enriched = df.copy()
    
    # Lógica de Segmentación
    def clasificar_segmento(membresia: float) -> Tuple[str, float]:
        if pd.isna(membresia) or membresia == 0: return "Básico", 800.0
        if 0 < membresia < 90: return "Básico", 800.0
        if 90 <= membresia < 250: return "Intermedio", 2500.0
        if 250 <= membresia < 450: return "Premium", 6000.0
        return "Elite", 12000.0
    
    # Aplicar clasificación
    segmentos = df_enriched["membresia_anual_soles"].apply(lambda x: clasificar_segmento(x if pd.notna(x) else 0.0))
    df_enriched["segmento_gasto"] = [s[0] for s in segmentos]
    df_enriched["gasto_mensual_estimado_soles"] = [s[1] for s in segmentos]
    df_enriched["gasto_anual_estimado_soles"] = df_enriched["gasto_mensual_estimado_soles"] * 12
    
    # Parámetros financieros fijos
    df_enriched["valor_milla_soles"] = 0.03
    tasa_millas = df_enriched["millas_por_dolar_consumo"].fillna(1.0)
    tipo_cambio = 3.75
    
    # Cálculos
    df_enriched["millas_anuales_generadas"] = ((df_enriched["gasto_anual_estimado_soles"] / tipo_cambio) * tasa_millas).round(0)
    df_enriched["valor_millas_anual_soles"] = (df_enriched["millas_anuales_generadas"] * df_enriched["valor_milla_soles"]).round(2)
    df_enriched["valor_bono_bienvenida_soles"] = (df_enriched["bono_bienvenida_millas"] * df_enriched["valor_milla_soles"]).round(2)
    
    # Valor Neto (El KPI más importante)
    df_enriched["valor_neto_primer_anio_soles"] = (df_enriched["valor_millas_anual_soles"] + df_enriched["valor_bono_bienvenida_soles"] - df_enriched["membresia_anual_soles"]).round(2)
    df_enriched["valor_neto_anual_recurrente_soles"] = (df_enriched["valor_millas_anual_soles"] - df_enriched["membresia_anual_soles"]).round(2)
    
    # Optimización de Memoria (Downcasting)
    cols_float = df_enriched.select_dtypes(include=['float64']).columns
    df_enriched[cols_float] = df_enriched[cols_float].apply(pd.to_numeric, downcast='float')
    df_enriched['segmento_gasto'] = df_enriched['segmento_gasto'].astype('category')
    
    log.info(f"📈 Enriquecimiento completado. Valor promedio neto 1er año: S/ {df_enriched['valor_neto_primer_anio_soles'].mean():.2f}")
    return df_enriched