import pandera as pa
from pandera import Column, DataFrameSchema

# =========================================================
# 1. ESQUEMA MAESTRO DE TARJETAS DE CRÉDITO
# =========================================================
esquema_tarjetas = DataFrameSchema({
    # --- Columnas base de extracción ---
    "banco": Column(str, nullable=True),
    "producto_nombre": Column(str, nullable=True),
    "nombre_tarjeta": Column(str, nullable=True), # Mantenido por compatibilidad
    "categoria": Column(str, nullable=True),
    "tcea_maxima": Column(float, nullable=True),
    "membresia_anual_soles": Column(float, nullable=True),
    "requisito_exoneracion_membresia": Column(str, nullable=True),
    "beneficio_principal": Column(str, nullable=True),
    "beneficios_clave": Column(str, nullable=True),
    "ingreso_minimo_requerido": Column(float, nullable=True),
    
    # --- Columnas de métricas y cálculos (KPIs) ---
    "segmento_gasto": Column(str, nullable=True),
    "millas_por_dolar_consumo": Column(float, nullable=True),
    "bono_bienvenida_millas": Column(float, nullable=True),
    "gasto_mensual_estimado_soles": Column(float, nullable=True),
    "gasto_anual_estimado_soles": Column(float, nullable=True),
    "valor_milla_soles": Column(float, nullable=True),
    "millas_anuales_generadas": Column(float, nullable=True),
    "valor_millas_anual_soles": Column(float, nullable=True),
    "valor_bono_bienvenida_soles": Column(float, nullable=True),
    "valor_neto_primer_anio_soles": Column(float, nullable=True),
    "valor_neto_anual_recurrente_soles": Column(float, nullable=True),
    
    # --- Metadatos ---
    "url_origen": Column(str, nullable=True),
    "url_detalle": Column(str, nullable=True),
    "fecha_scraping": Column(str, nullable=True),
    "fecha_extraccion": Column(str, nullable=True),
    "fuente": Column(str, nullable=True)
}, coerce=True)

# Alias por si algún script importa 'esquema_tc' en lugar de 'esquema_tarjetas'
esquema_tc = esquema_tarjetas 


# =========================================================
# 2. ESQUEMA: CUENTAS DE AHORRO
# =========================================================
esquema_ahorros = pa.DataFrameSchema({
    "banco": Column(str, nullable=False),
    "producto_nombre": Column(str, nullable=False),
    "trea_soles": Column(float, nullable=True),
    "monto_minimo_apertura": Column(float, nullable=True),
    "mantenimiento_mensual": Column(float, nullable=True),
    "requisito_mantenimiento_gratis": Column(str, nullable=True),
    "retiros_gratuitos_cajero_propio": Column(str, nullable=True),
    "retiros_gratuitos_ventanilla": Column(str, nullable=True),
    "fecha_scraping": Column(str, nullable=False),
    "url_origen": Column(str, nullable=False)
}, coerce=True)


# =========================================================
# 3. ESQUEMA: DEPÓSITOS A PLAZO
# =========================================================
esquema_plazos = pa.DataFrameSchema({
    "banco": Column(str, nullable=False),
    "producto_nombre": Column(str, nullable=False),
    "plazo_dias_min": Column(int, nullable=True),
    "plazo_dias_max": Column(int, nullable=True),
    "monto_min": Column(float, nullable=True),
    "monto_max": Column(float, nullable=True),
    "trea_soles": Column(float, nullable=True),
    "pago_interes_frecuencia": Column(str, nullable=True),
    "penalizacion_cancelacion_anticipada": Column(str, nullable=True),
    "fecha_scraping": Column(str, nullable=False),
    "url_origen": Column(str, nullable=False)
}, coerce=True)