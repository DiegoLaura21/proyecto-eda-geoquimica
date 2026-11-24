"""Estadísticas de EDA y exportación, con los censurados en estados separados."""

from math import ceil

import pandas as pd

from analitos import DERECHA, DETECTADO, IZQUIERDA


def escribir_csv(tabla, ruta, *, indice=False):
    tabla.to_csv(ruta, index=indice, encoding="utf-8-sig", float_format="%.10g")


def resumir(analitos):
    filas = []
    for (e, grupo), datos in analitos.groupby(["elemento", "grupo"], sort=False):
        estados = datos["estado_uso"]
        valores = datos.loc[estados.eq(DETECTADO), "valor_uso"]
        q = valores.quantile([0.25, 0.50, 0.75, 0.95, 0.99])
        filas.append({
            "elemento": e, "grupo": grupo, "unidad": datos["unidad"].iat[0], "n": len(datos),
            "detectados": len(valores), "censura_izquierda": estados.eq(IZQUIERDA).sum(),
            "censura_derecha": estados.eq(DERECHA).sum(), "faltantes": estados.eq("faltante").sum(),
            "excluidos": estados.eq("excluido").sum(),
            "otros_invalidos": (~estados.isin([DETECTADO, IZQUIERDA, DERECHA, "faltante", "excluido"])).sum(),
            "deteccion_pct": 100 * len(valores) / len(datos), "min_detectados": valores.min(),
            "p25_detectados": q.loc[0.25], "p50_detectados": q.loc[0.50],
            "p75_detectados": q.loc[0.75], "p95_detectados": q.loc[0.95],
            "p99_detectados": q.loc[0.99], "max_detectados": valores.max(),
            "marcas_mad_original": datos["senal_estadistica"].ne("").sum(),
            "pendientes_revision": (datos["motivos_revision"].ne("") & datos["accion"].eq("")).sum(),
        })
    return pd.DataFrame(filas)


def correlaciones(analitos, min_pares):
    detectados = analitos.pivot(index="muestra_id", columns="elemento", values="valor_uso")
    orden = analitos["elemento"].drop_duplicates().tolist()
    detectados = detectados.reindex(columns=orden)
    presentes = detectados.notna().astype("int64")
    n = presentes.T @ presentes
    return detectados.corr(method="spearman", min_periods=min_pares), n


def sensibilidad_oro(analitos):
    oro = analitos.loc[analitos["elemento"].eq("Au")]
    filas = []
    for grupo, datos in oro.groupby("grupo", sort=False):
        valores = datos.loc[datos["estado_uso"].eq(DETECTADO), "valor_uso"].sort_values()
        n = len(valores)
        if not n:
            continue
        k = ceil(0.01 * n)
        cola = valores.iloc[-k:]
        referencia = valores.iloc[:-k]
        filas.append({
            "grupo": grupo, "unidad": datos["unidad"].iat[0], "n_detectados": n,
            "n_cola_superior": k, "media_detectados": valores.mean(),
            "mediana_detectados": valores.median(),
            "media_ilustrativa_sin_cola": referencia.mean(),
            "pct_suma_concentraciones_en_cola": 100 * (cola / valores.max()).sum() / (valores / valores.max()).sum(),
        })
    return pd.DataFrame(filas, columns=[
        "grupo", "unidad", "n_detectados", "n_cola_superior", "media_detectados", "mediana_detectados",
        "media_ilustrativa_sin_cola", "pct_suma_concentraciones_en_cola",
    ])


def exportar_ancha(muestras, analitos, config):
    elementos = config["elementos"]
    columnas_analiticas = [r["columna"] for r in elementos.values()]
    metadatos = muestras.drop(columns=columnas_analiticas).copy()
    for e, datos in analitos.groupby("elemento", sort=False):
        columna = f"{e}_{elementos[e]['unidad_salida']}"
        if columna in metadatos.columns:
            raise ValueError(f"La columna de salida {columna} coincide con un campo de metadatos.")
        d = datos.set_index("muestra_id").reindex(muestras[config["columna_id"]])
        valores = []
        for estado, n, limite in zip(d["estado_uso"], d["valor_uso"], d["limite_uso"]):
            if estado == DETECTADO:
                valores.append(f"{n:.12g}")
            elif estado in {IZQUIERDA, DERECHA}:
                comparador = "<" if estado == IZQUIERDA else ">"
                valores.append(f"{comparador}{limite:.12g}")
            else:
                valores.append("")
        metadatos[columna] = valores
    return metadatos

