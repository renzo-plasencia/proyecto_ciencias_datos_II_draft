# logic_layer.py
# Capa de lógica para el dashboard Inicio (home)
# Responsabilidad: transformar y calcular métricas sobre los DataFrames Gold

import pandas as pd


def calcular_indice_banco(cuentas_df: pd.DataFrame, dpf_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula el índice de cada banco: 50% rentabilidad (TREA promedio) + 50% accesibilidad.
    Parámetros: cuentas_df, dpf_df (DataFrames Gold de cuentas y depósitos a plazo).
    Retorna: pd.DataFrame con banco, rentabilidad_promedio, accesibilidad e indice_banco.
    """
    trea_cuentas = (
        cuentas_df.groupby("banco")["trea_num"]
        .mean()
        .reset_index(name="trea_promedio_cuentas")
    )
    trea_dpf = (
        dpf_df.groupby("banco")["trea_num"]
        .mean()
        .reset_index(name="trea_promedio_dpf")
    )
    rentabilidad = trea_cuentas.merge(trea_dpf, on="banco", how="outer")
    rentabilidad["rentabilidad_promedio"] = rentabilidad[
        ["trea_promedio_cuentas", "trea_promedio_dpf"]
    ].mean(axis=1)

    cuentas_tmp = cuentas_df.copy()
    dpf_tmp = dpf_df.copy()
    dpf_tmp["es_costo_cero"] = dpf_tmp["trea_num"] > 0

    productos = pd.concat(
        [
            cuentas_tmp[["banco", "es_costo_cero"]],
            dpf_tmp[["banco", "es_costo_cero"]],
        ],
        ignore_index=True,
    )
    accesibilidad = (
        productos.groupby("banco")
        .agg(
            productos_gratuitos=("es_costo_cero", "sum"),
            total_productos=("es_costo_cero", "count"),
        )
        .reset_index()
    )
    accesibilidad["accesibilidad"] = (
        accesibilidad["productos_gratuitos"] / accesibilidad["total_productos"]
    )

    indice_banco = rentabilidad.merge(accesibilidad, on="banco")

    indice_banco["rentabilidad_norm"] = (
        indice_banco["rentabilidad_promedio"] - indice_banco["rentabilidad_promedio"].min()
    ) / (
        indice_banco["rentabilidad_promedio"].max() - indice_banco["rentabilidad_promedio"].min()
    )
    indice_banco["accesibilidad_norm"] = (
        indice_banco["accesibilidad"] - indice_banco["accesibilidad"].min()
    ) / (
        indice_banco["accesibilidad"].max() - indice_banco["accesibilidad"].min()
    )
    indice_banco["indice_banco"] = (
        0.5 * indice_banco["rentabilidad_norm"] + 0.5 * indice_banco["accesibilidad_norm"]
    )

    return indice_banco.sort_values("indice_banco", ascending=False).reset_index(drop=True)

def _normalizar(df, col_valor, col_producto, tipo):
        tmp = df[df[col_valor] > 0][[col_producto, "banco", col_valor]].copy()
        tmp = tmp.rename(columns={col_producto: "producto", col_valor: "valor_original"})
        tmp["tipo_producto"] = tipo
        tmp["rentabilidad_norm"] = (
            (tmp["valor_original"] - tmp["valor_original"].min())
            / (tmp["valor_original"].max() - tmp["valor_original"].min())
            * 100
        )
        return tmp

def calcular_rentabilidad_normalizada_por_producto(
    cuentas_df: pd.DataFrame, dpf_df: pd.DataFrame, tc_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Normaliza (0-100) la rentabilidad de cada producto dentro de su propia categoría,
    para poder compararlos en un solo gráfico agrupado por banco.
    Parámetros: cuentas_df, dpf_df, tc_df (los tres DataFrames Gold).
    Retorna: pd.DataFrame con producto, banco, tipo_producto, valor_original, rentabilidad_norm.
    """
    

    cuentas_norm = _normalizar(cuentas_df, "trea_num", "producto_nombre", "Cuenta de Ahorro")
    dpf_norm = _normalizar(dpf_df, "trea_num", "producto", "Depósito a Plazo")

    tc_tmp = tc_df.copy()
    tc_tmp["valor_neto_anual_recurrente_soles"] = pd.to_numeric(
        tc_tmp["valor_neto_anual_recurrente_soles"], errors="coerce"
    )
    tc_tmp = tc_tmp.dropna(subset=["valor_neto_anual_recurrente_soles"])
    tc_norm = _normalizar(
        tc_tmp, "valor_neto_anual_recurrente_soles", "nombre_tarjeta", "Tarjeta de Crédito"
    )

    return pd.concat([cuentas_norm, dpf_norm, tc_norm], ignore_index=True)


def calcular_kpis(cuentas_df: pd.DataFrame, dpf_df: pd.DataFrame, tc_df: pd.DataFrame,
                   indice_banco: pd.DataFrame) -> dict:
    """
    Calcula los 3 KPIs del home: mejor TREA, banco líder y TC más rentable.
    Parámetros: los tres DataFrames Gold y el resultado de calcular_indice_banco().
    Retorna: dict con sub-diccionarios 'mejor_trea', 'banco_lider', 'tc_top'.
    """
    # --- Producto con mejor TREA ---
    todos_trea = pd.concat(
        [
            cuentas_df[["producto_nombre", "banco", "trea_num"]].rename(
                columns={"producto_nombre": "producto"}
            ),
            dpf_df[["producto", "banco", "trea_num"]],
        ],
        ignore_index=True,
    )
    todos_trea = todos_trea[todos_trea["trea_num"] > 0]
    mejor_trea = todos_trea.loc[todos_trea["trea_num"].idxmax()]
    promedio_mercado = todos_trea["trea_num"].mean()
    multiplo = mejor_trea["trea_num"] / promedio_mercado if promedio_mercado else 0

    # --- Banco líder ---
    banco_lider = indice_banco.iloc[0]

    # --- TC más rentable ---

    tc_tmp = tc_df.copy()

    tc_tmp["valor_neto_anual_recurrente_soles"] = pd.to_numeric(
        tc_tmp["valor_neto_anual_recurrente_soles"],
        errors="coerce"
    )

    # Eliminar tarjetas sin banco

    tc_tmp = tc_tmp.dropna(subset=["banco"])

    tc_tmp = tc_tmp[
        tc_tmp["banco"].astype(str).str.strip() != ""
    ]

    # Eliminar valores nulos del indicador

    tc_tmp = tc_tmp.dropna(
        subset=["valor_neto_anual_recurrente_soles"]
    )

    # Conservar únicamente valores positivos

    tc_tmp = tc_tmp[
        tc_tmp["valor_neto_anual_recurrente_soles"] > 0
    ]

    # Obtener la tarjeta más rentable

    tc_top = tc_tmp.loc[
        tc_tmp["valor_neto_anual_recurrente_soles"].idxmax()
    ]

    return {
        "mejor_trea": {
            "producto": mejor_trea["producto"],
            "banco": mejor_trea["banco"],
            "trea": mejor_trea["trea_num"],
            "multiplo": multiplo,
        },
        "banco_lider": {
            "banco": banco_lider["banco"],
            "indice": banco_lider["indice_banco"],
        },
        "tc_top": {
            "tarjeta": tc_top["nombre_tarjeta"],
            "banco": tc_top["banco"],
            "valor": tc_top["valor_neto_anual_recurrente_soles"],
        },
    }

def obtener_metricas_cuentas_ahorro(cuentas_df: pd.DataFrame) -> dict:
    """
    Calcula el producto con mejor TREA y las proporciones de cuentas con/sin costo de mantenimiento.
    """
    df_valid = cuentas_df[cuentas_df["trea_num"] > 0].copy()
    
    if df_valid.empty:
        return {"mejor_cuenta": None, "distribucion_costos": pd.DataFrame()}

    # 1. Banco / Producto con mejor TREA
    idx_max = df_valid["trea_num"].idxmax()
    mejor_cuenta = df_valid.loc[idx_max]

    # 2. Con vs Sin costo de mantenimiento
    # 'es_costo_cero' puede venir como booleano (True/False) o como string ("VERDADERO"/"FALSO")
    if "es_costo_cero" in cuentas_df.columns:
        cuentas_df["tiene_costo"] = ~cuentas_df["es_costo_cero"].astype(str).str.upper().isin(["TRUE", "VERDADERO"])
    elif "mantenimiento_num" in cuentas_df.columns:
        cuentas_df["tiene_costo"] = cuentas_df["mantenimiento_num"] > 0
    else:
        cuentas_df["tiene_costo"] = False

    distribucion_costos = (
        cuentas_df.groupby("tiene_costo")
        .size()
        .reset_index(name="cantidad")
    )
    distribucion_costos["categoria"] = distribucion_costos["tiene_costo"].map(
        {True: "Con Costo", False: "Sin Costo (Gratis)"}
    )
    total = distribucion_costos["cantidad"].sum()
    distribucion_costos["porcentaje"] = (distribucion_costos["cantidad"] / total) * 100 if total > 0 else 0

    return {
        "mejor_cuenta": mejor_cuenta,
        "distribucion_costos": distribucion_costos
    }


def obtener_metricas_dpf(dpf_df: pd.DataFrame) -> dict:
    """
    Calcula el producto/banco con la mejor TREA en Depósitos a Plazo Fijo.
    """
    df_valid = dpf_df[dpf_df["trea_num"] > 0].copy()
    
    if df_valid.empty:
        return {"mejor_dpf": None}

    idx_max = df_valid["trea_num"].idxmax()
    mejor_dpf = df_valid.loc[idx_max]

    return {
        "mejor_dpf": mejor_dpf
    }

def obtener_metricas_tc(tc_df: pd.DataFrame) -> dict:
    """
    Calcula la tarjeta de crédito con mejor valor neto anual recurrente.
    """
    tc_tmp = tc_df.copy()
    
    # Limpieza básica
    tc_tmp["valor_neto_anual_recurrente_soles"] = pd.to_numeric(
        tc_tmp["valor_neto_anual_recurrente_soles"], errors="coerce"
    )
    tc_tmp = tc_tmp.dropna(subset=["banco", "valor_neto_anual_recurrente_soles"])
    tc_tmp = tc_tmp[
        (tc_tmp["banco"].astype(str).str.strip() != "") & 
        (tc_tmp["valor_neto_anual_recurrente_soles"] > 0)
    ]
    
    if tc_tmp.empty:
        return {"mejor_tc": None}

    idx_max = tc_tmp["valor_neto_anual_recurrente_soles"].idxmax()
    mejor_tc = tc_tmp.loc[idx_max]

    return {
        "mejor_tc": mejor_tc
    }

def calcular_ranking_costo_cero(cuentas_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula el número de cuentas de ahorro con mantenimiento cero por banco.
    Parámetros: cuentas_df (pd.DataFrame) datos Gold de cuentas de ahorro.
    Retorna: pd.DataFrame con columnas [banco, num_cuentas], ordenado ascendente.
    """
    ranking = (
        cuentas_df[cuentas_df["es_costo_cero"] == True]
        .groupby("banco")
        .size()
        .reset_index(name="num_cuentas")
        .sort_values("num_cuentas", ascending=True)
    )
    return ranking


def calcular_top_trea_costo_cero(cuentas_df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """
    Obtiene el top N de cuentas con mantenimiento cero ordenadas por mejor TREA.
    Parámetros: cuentas_df (pd.DataFrame), top_n (int) cantidad de filas a devolver.
    Retorna: pd.DataFrame con columnas [banco, producto_nombre, trea_soles, url_origen].
    """
    top = (
        cuentas_df[cuentas_df["mantenimiento_num"] == 0]
        .sort_values("trea_soles", ascending=False)
        .head(top_n)
        [["banco", "producto_nombre", "trea_soles", "url_origen"]]
    )
    return top

def calcular_ranking_membresia_tc(tc_df: pd.DataFrame) -> pd.DataFrame:
    """
    Ordena todas las tarjetas de crédito por costo de membresía anual, de mayor a menor.
    Parámetros: tc_df (pd.DataFrame) datos Gold de tarjetas de crédito.
    Retorna: pd.DataFrame con columnas [banco, nombre_tarjeta, membresia_num,
             requisito_exoneracion_membresia], ordenado descendente por membresia_num.
    """
    ranking = (
        tc_df.loc[
            tc_df["membresia_num"] > 0,
            ["banco", "nombre_tarjeta", "membresia_num", "requisito_exoneracion_membresia"]
        ]
        .sort_values("membresia_num", ascending=False)
        .reset_index(drop=True)
    )
    return ranking


def obtener_tarjeta_mas_costosa(tc_df: pd.DataFrame) -> pd.Series:
    """
    Identifica la tarjeta individual con el mayor costo de membresía anual.
    Parámetros: tc_df (pd.DataFrame) datos Gold de tarjetas de crédito.
    Retorna: pd.Series con los datos de esa tarjeta (fila completa).
    """
    return tc_df.sort_values("membresia_num", ascending=False).iloc[0]


def preparar_tc_primer_sueldo(tc_df: pd.DataFrame, ingreso_maximo: float = 3000) -> pd.DataFrame:
    """
    Prepara y FILTRA el dataframe de tarjetas a solo aquellas con ingreso
    mínimo requerido menor a ingreso_maximo, deduplicando por tarjeta única.
    No usa apta_primer_sueldo por venir con datos inconsistentes en la fuente.
    Parámetros: tc_df (pd.DataFrame) datos Gold de tarjetas de crédito.
                ingreso_maximo (float) tope de ingreso mínimo (default S/3,000).
    Retorna: pd.DataFrame con columnas [banco, nombre_tarjeta, ingreso_min_num,
             membresia_num], solo con ingreso_min_num < ingreso_maximo.
    """
    tmp = tc_df.copy()
    tmp = tmp.drop_duplicates(subset=["banco", "nombre_tarjeta"])
    tmp = tmp.dropna(subset=["banco", "nombre_tarjeta", "ingreso_min_num", "membresia_num"])
    tmp = tmp[tmp["banco"].astype(str).str.strip() != ""]

    tmp = tmp[tmp["ingreso_min_num"] < ingreso_maximo]

    cols = ["banco", "nombre_tarjeta", "ingreso_min_num", "membresia_num"]
    return tmp[cols]


def obtener_mejor_tarjeta_primer_sueldo(tc_primer_sueldo: pd.DataFrame) -> pd.Series:
    """
    Identifica la mejor tarjeta de entrada dentro del subconjunto ya filtrado:
    menor membresía anual (y en empate, menor ingreso mínimo).
    Parámetros: tc_primer_sueldo (pd.DataFrame) resultado de preparar_tc_primer_sueldo().
    Retorna: pd.Series con la fila de la mejor tarjeta, o None si está vacío.
    """
    if tc_primer_sueldo.empty:
        return None
    return tc_primer_sueldo.sort_values(["membresia_num", "ingreso_min_num"], ascending=[True, True]).iloc[0]