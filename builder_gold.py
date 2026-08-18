import os
import re
from pathlib import Path
import pandas as pd
import numpy as np

# CONFIGURACIÓN DE RUTAS
ROOT_DIR = Path(__file__).parent
SILVER_DIR = ROOT_DIR / "output" / "silver"
GOLD_DIR = ROOT_DIR / "output" / "gold"


# FUNCIONES AUXILIARES DE LIMPIEZA

def extraer_numero(texto):
    """Extrae el primer número (entero o decimal) de un texto."""
    if pd.isna(texto):
        return 0.0
    texto_str = str(texto).replace(',', '')
    numeros = re.findall(r"[-+]?\d*\.\d+|\d+", texto_str)
    return float(numeros[0]) if numeros else 0.0

def detectar_palabra_clave(texto, palabras_clave):
    """Busca si alguna palabra clave existe en el texto (para categorizar)."""
    if pd.isna(texto):
        return False
    texto_str = str(texto).lower()
    return any(palabra in texto_str for palabra in palabras_clave)

# TRANSFORMACIONES DE LA CAPA GOLD

def consolidar_capa_gold():
    print(">>> INICIANDO CREACIÓN DE CAPA GOLD (CON LÓGICA DE NEGOCIO) <<<")
    GOLD_DIR.mkdir(parents=True, exist_ok=True)


    # 1. TARJETAS DE CRÉDITO (El Dilema de la 1ra Tarjeta / Consumidor Digital)

    archivos_tc = list(SILVER_DIR.glob("*tarjetas*.parquet")) + list(SILVER_DIR.glob("tc_*.parquet"))
    if archivos_tc:
        df_tc = pd.concat([pd.read_parquet(f) for f in archivos_tc], ignore_index=True)
        df_tc = df_tc.drop_duplicates(subset=['banco', 'nombre_tarjeta'])
        # PARCHE: Eliminar filas fantasma que no tengan banco asignado
        df_tc = df_tc.dropna(subset=['banco', 'nombre_tarjeta'])
        df_tc = df_tc[df_tc['banco'].astype(str).str.strip() != 'None']
        df_tc = df_tc[df_tc['banco'].astype(str).str.strip() != '']
    
        
        
        # INGENIERÍA DE CARACTERÍSTICAS (FEATURE ENGINEERING)
        # 1. Limpiar Costos e Ingresos para que sean operables numéricamente
        col_ingreso = 'ingreso_minimo' if 'ingreso_minimo' in df_tc.columns else df_tc.columns[df_tc.columns.str.contains('ingreso', case=False)][0]
        col_membresia = 'membresia' if 'membresia' in df_tc.columns else df_tc.columns[df_tc.columns.str.contains('membresia|costo', case=False)][0]
        
        df_tc['ingreso_min_num'] = df_tc[col_ingreso].apply(extraer_numero)
        df_tc['membresia_num'] = df_tc[col_membresia].apply(extraer_numero)
        
        # 2. Banderas para el Dashboard (Filtros rápidos)
        df_tc['es_membresia_cero'] = df_tc['membresia_num'] == 0
        df_tc['apta_primer_sueldo'] = df_tc['ingreso_min_num'] <= 1500
        
        # 3. Categorización de Beneficios (Millas/Puntos/Cashback)
        col_beneficios = 'beneficios' if 'beneficios' in df_tc.columns else df_tc.columns[df_tc.columns.str.contains('beneficio|detalle', case=False)][0]
        df_tc['acumula_millas_puntos'] = df_tc[col_beneficios].apply(lambda x: detectar_palabra_clave(x, ['milla', 'punto', 'latam', 'reward']))
        df_tc['beneficio_vip'] = df_tc[col_beneficios].apply(lambda x: detectar_palabra_clave(x, ['vip', 'salones', 'aeropuerto', 'priority']))
        
        df_tc.to_parquet(GOLD_DIR / "master_tarjetas_credito.parquet", index=False)
        print(f"✅ Tarjetas Gold: {len(df_tc)} registros procesados y enriquecidos.")

    # 2. CUENTAS DE AHORRO (El Dilema del Uso Diario)
    
    archivos_ahorro = list(SILVER_DIR.glob("*ahorros*.parquet")) + list(SILVER_DIR.glob("ahorro*.parquet"))
    if archivos_ahorro:
        df_ahorro = pd.concat([pd.read_parquet(f) for f in archivos_ahorro], ignore_index=True)
        df_ahorro = df_ahorro.drop_duplicates(ignore_index=True)
        
        # INGENIERÍA DE CARACTERÍSTICAS
        col_mantenimiento = 'mantenimiento' if 'mantenimiento' in df_ahorro.columns else df_ahorro.columns[df_ahorro.columns.str.contains('mantenimiento', case=False)][0]
        col_trea = 'trea' if 'trea' in df_ahorro.columns else df_ahorro.columns[df_ahorro.columns.str.contains('trea|tasa', case=False)][0]
        
        df_ahorro['mantenimiento_num'] = df_ahorro[col_mantenimiento].apply(extraer_numero)
        df_ahorro['trea_num'] = df_ahorro[col_trea].apply(extraer_numero)
        
        # Bandera de Costo Cero para el filtro rápido
        df_ahorro['es_costo_cero'] = df_ahorro['mantenimiento_num'] == 0
        
        df_ahorro.to_parquet(GOLD_DIR / "master_cuentas_ahorro.parquet", index=False)
        print(f"✅ Ahorros Gold: {len(df_ahorro)} registros procesados y enriquecidos.")

   
    # 3. DEPÓSITOS A PLAZO FIJO (El Simulador Conservador)
    
    archivos_dpf = list(SILVER_DIR.glob("*plazo_fijo*.parquet"))
    if archivos_dpf:
        df_dpf = pd.concat([pd.read_parquet(f) for f in archivos_dpf], ignore_index=True)
        df_dpf = df_dpf.drop_duplicates()
        
        # Aseguramos que las columnas clave sean numéricas para poder operar la fórmula de interés compuesto en el dashboard
        cols_numericas = ['trea', 'monto_minimo', 'monto_maximo', 'plazo_dias']
        for col in cols_numericas:
            # Busca la columna que contenga el nombre y la convierte
            col_real = df_dpf.columns[df_dpf.columns.str.contains(col, case=False)]
            if len(col_real) > 0:
                df_dpf[f'{col}_num'] = df_dpf[col_real[0]].apply(extraer_numero)

        df_dpf.to_parquet(GOLD_DIR / "master_plazo_fijo.parquet", index=False)
        print(f"✅ Plazo Fijo Gold: {len(df_dpf)} registros preparados para el simulador.")

    print("\n🏁 ¡Capa Gold finalizada con éxito! La data está lista como Producto Final.")

if __name__ == "__main__":
    consolidar_capa_gold()