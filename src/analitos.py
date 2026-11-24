"""Lectura, normalización, detección robusta y decisiones sobre concentraciones."""

import csv
import json
from math import isfinite
import re

import numpy as np
import pandas as pd


FACTOR_PPM = {"ppb": 0.001, "ppm": 1.0, "mg/kg": 1.0, "g/t": 1.0, "%": 10000.0}
NUMERO = re.compile(r"([<>]=?)?\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)")
DETECTADO = "detectado"
IZQUIERDA = "censura_izquierda"
DERECHA = "censura_derecha"
COLUMNAS_DECISION = ["muestra_id", "elemento", "valor_original", "accion", "valor_corregido", "evidencia"]


def leer_csv(ruta, requeridas):
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        encabezados = next(csv.reader(archivo), [])
    if not encabezados or len(set(encabezados)) != len(encabezados):
        raise ValueError(f"{ruta.name}: se requieren encabezados únicos.")
    datos = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if not isinstance(datos.index, pd.RangeIndex):
        raise ValueError(f"{ruta.name}: hay filas con más campos que el encabezado.")
    faltantes = set(requeridas) - set(datos.columns)
    if faltantes:
        raise ValueError(f"{ruta.name}: faltan columnas {', '.join(sorted(faltantes))}.")
    return datos


def numero_config(x, nombre, minimo, maximo=float("inf")):
    if type(x) not in (int, float) or not isfinite(x) or not minimo <= x <= maximo:
        raise ValueError(f"{nombre}: se esperaba un número entre {minimo:g} y {maximo:g}.")


def cargar_config(ruta):
    with ruta.open(encoding="utf-8-sig") as archivo:
        c = json.load(archivo)
    if not isinstance(c, dict):
        raise ValueError("La configuración debe ser un objeto JSON.")
    for k in ("proyecto", "columna_id", "columna_lote"):
        if not isinstance(c.get(k), str) or not c[k].strip():
            raise ValueError(f"Configura {k} como texto.")
    if c["columna_id"] == c["columna_lote"]:
        raise ValueError("Las columnas de ID y lote deben ser distintas.")
    grupos = c.get("grupos")
    if not isinstance(grupos, list) or any(not isinstance(g, str) or not g.strip() for g in grupos):
        raise ValueError("Configura grupos como una lista de nombres de columnas o [].")
    if len(set(grupos)) != len(grupos) or c["columna_id"] in grupos:
        raise ValueError("Los grupos deben ser únicos y distintos del ID de muestra.")
    coords = c.get("columnas_coordenadas")
    if coords is not None and (
        not isinstance(coords, list) or len(coords) != 2
        or any(not isinstance(k, str) or not k.strip() for k in coords) or coords[0] == coords[1]
    ):
        raise ValueError("Indica dos columnas de coordenadas o usa null.")
    minimo = c.get("muestra_min_detecciones")
    numero_config(minimo, "muestra_min_detecciones", 5)
    if type(minimo) is not int:
        raise ValueError("muestra_min_detecciones debe ser entero.")
    numero_config(c.get("fraccion_min_detectados"), "fraccion_min_detectados", 0, 1)
    numero_config(c.get("umbral_mad"), "umbral_mad", 0.1)
    elementos = c.get("elementos")
    if not isinstance(elementos, dict) or not elementos:
        raise ValueError("Configura al menos un elemento.")
    columnas = []
    for elemento, regla in elementos.items():
        if not elemento.strip() or not isinstance(regla, dict) or not regla.get("columna"):
            raise ValueError("Cada elemento requiere un nombre y una columna de entrada.")
        if not isinstance(regla["columna"], str):
            raise ValueError(f"{elemento}: la columna debe ser texto.")
        columnas.append(regla["columna"])
        for unidad in ("unidad_entrada", "unidad_salida"):
            if regla.get(unidad) not in FACTOR_PPM:
                raise ValueError(f"{elemento}: unidad desconocida en {unidad}.")
        lr = regla.get("limite_reporte")
        if lr is not None:
            numero_config(lr, f"{elemento}.limite_reporte", 1e-15)
    if len(set(columnas)) != len(columnas) or set(columnas) & {c["columna_id"], c["columna_lote"], *grupos}:
        raise ValueError("Cada elemento requiere una columna de concentración única.")
    q = c.get("qaqc")
    if not isinstance(q, dict):
        raise ValueError("Configura el bloque qaqc.")
    for k in ("blanco_max_en_lr", "duplicado_min_en_lr", "rpd_max_pct"):
        numero_config(q.get(k), k, 0.001, 200 if k == "rpd_max_pct" else float("inf"))
    return c


def interpretar(texto, lr=None):
    """Regresa estado, valor detectado y límite. Conserva la distinción entre ambos."""
    texto = texto.strip()
    codigo = texto.upper()
    if codigo in {"", "NA", "N/A", "NULL", "SIN ENSAYO"}:
        return "faltante", np.nan, np.nan
    if codigo in {"ND", "BDL", "N.D."}:
        return (IZQUIERDA, np.nan, lr) if lr is not None else ("nd_sin_limite", np.nan, np.nan)
    coincidencia = NUMERO.fullmatch(texto)
    if not coincidencia:
        return "formato_invalido", np.nan, np.nan
    signo, literal = coincidencia.groups()
    n = float(literal)
    if not isfinite(n):
        return "formato_invalido", np.nan, np.nan
    if n <= 0:
        return ("cero_revisar" if n == 0 else "negativo_revisar"), np.nan, np.nan
    if signo:
        return (IZQUIERDA if signo.startswith("<") else DERECHA), np.nan, n
    return DETECTADO, n, np.nan


def factor_unidad(regla):
    return FACTOR_PPM[regla["unidad_entrada"]] / FACTOR_PPM[regla["unidad_salida"]]


def preparar_muestras(ruta, c):
    id_col, lote_col, grupos = c["columna_id"], c["columna_lote"], c["grupos"]
    columnas = [r["columna"] for r in c["elementos"].values()]
    muestras = leer_csv(ruta, [id_col, lote_col, *grupos, *columnas, *(c.get("columnas_coordenadas") or [])])
    if muestras.empty:
        raise ValueError("La tabla no contiene muestras.")
    for col in dict.fromkeys([id_col, lote_col, *grupos]):
        muestras[col] = muestras[col].str.strip()
        if muestras[col].eq("").any():
            raise ValueError(f"No se permiten celdas vacías en {col}.")
    if muestras[id_col].duplicated().any():
        ids = muestras.loc[muestras[id_col].duplicated(keep=False), id_col].unique()
        raise ValueError(f"ID de muestra repetido: {', '.join(ids[:8])}. Resuelve el cruce antes del EDA.")
    etiqueta = muestras[grupos].agg(" / ".join, axis=1) if grupos else pd.Series("Todas", index=muestras.index)
    if grupos and muestras[grupos].drop_duplicates().shape[0] != etiqueta.nunique():
        raise ValueError("Dos grupos producen la misma etiqueta. Evita ' / ' dentro de los nombres combinados.")
    partes = []
    for e, regla in c["elementos"].items():
        origen = muestras[regla["columna"]]
        tripletas = origen.map(lambda t: interpretar(t, regla.get("limite_reporte")))
        valores = pd.DataFrame(tripletas.tolist(), columns=["estado_original", "valor_original_num", "limite"])
        with np.errstate(over="ignore", under="ignore"):
            valores[["valor_original_num", "limite"]] *= factor_unidad(regla)
        numerico = valores[["valor_original_num", "limite"]]
        invalido = (np.isinf(numerico) | numerico.eq(0)).any(axis=1)
        valores.loc[invalido, "estado_original"] = "conversion_invalida"
        valores.loc[invalido, ["valor_original_num", "limite"]] = np.nan
        partes.append(valores.assign(
            muestra_id=muestras[id_col], lote=muestras[lote_col], grupo=etiqueta,
            elemento=e, unidad=regla["unidad_salida"], valor_original=origen,
        ))
    analitos = pd.concat(partes, ignore_index=True)
    return muestras, analitos


def marcar_extremos(analitos, c):
    analitos["z_mad_log10"] = np.nan
    analitos["evaluacion_mad"] = "no_aplica"
    analitos["senal_estadistica"] = ""
    res = []
    for (e, grupo), todo in analitos.groupby(["elemento", "grupo"], sort=False):
        datos = todo.loc[todo["estado_original"].eq(DETECTADO), "valor_original_num"]
        n = len(datos)
        fraccion = n / len(todo)
        med = mad = np.nan
        if n < c["muestra_min_detecciones"] or fraccion < c["fraccion_min_detectados"]:
            estado = "datos_insuficientes"
        else:
            log = np.log10(datos)
            med = log.median()
            mad = (log - med).abs().median()
            estado = "evaluado" if mad > 1e-12 else "mad_cero"
        analitos.loc[todo.index, "evaluacion_mad"] = estado
        if estado == "evaluado":
            z = 0.67448975 * (log - med) / mad
            analitos.loc[z.index, "z_mad_log10"] = z
            analitos.loc[z[z >= c["umbral_mad"]].index, "senal_estadistica"] = "extremo_alto"
            analitos.loc[z[z <= -c["umbral_mad"]].index, "senal_estadistica"] = "extremo_bajo"
        res.append([e, grupo, len(todo), n, fraccion, med, mad, c["umbral_mad"], estado])
    return pd.DataFrame(res, columns=[
        "elemento", "grupo", "n", "detectados", "fraccion_detectados", "mediana_log10",
        "mad_log10", "umbral", "estado",
    ])


def marcar_motivos(analitos):
    estados = analitos["estado_original"]
    motivos = pd.DataFrame({
        "dato": estados.where(~estados.isin([DETECTADO, IZQUIERDA, "faltante"]), ""),
        "estadistica": analitos["senal_estadistica"],
        "lote": analitos["qaqc_lote"].map({"alerta": "control_lote_alerta", "revisar": "control_lote_revisar"}).fillna(""),
        "duplicado": analitos["qaqc_muestra"].map({"alerta": "duplicado_alerta", "revisar": "duplicado_revisar"}).fillna(""),
    })
    analitos["motivos_revision"] = motivos.agg(lambda fila: " | ".join(filter(None, fila)), axis=1)


def aplicar_decisiones(analitos, ruta):
    analitos["valor_uso"] = analitos["valor_original_num"]
    analitos["limite_uso"] = analitos["limite"]
    analitos["estado_uso"] = analitos["estado_original"]
    analitos["accion"] = ""
    analitos["evidencia"] = ""
    if ruta is None:
        return
    decisiones = leer_csv(ruta, COLUMNAS_DECISION)
    for k in ["muestra_id", "elemento", "accion", "evidencia", "valor_corregido"]:
        decisiones[k] = decisiones[k].str.strip()
    decisiones = decisiones.loc[decisiones["accion"].ne("")]
    if decisiones.duplicated(["muestra_id", "elemento"]).any():
        raise ValueError("Hay decisiones duplicadas para una misma muestra y elemento.")
    indices = pd.Series(analitos.index, index=pd.MultiIndex.from_frame(analitos[["muestra_id", "elemento"]]))
    for f in decisiones.itertuples(index=False):
        clave = (f.muestra_id, f.elemento)
        if clave not in indices.index:
            raise ValueError(f"Decisión sin muestra y elemento correspondientes: {clave}.")
        i = indices.loc[clave]
        if f.valor_original != analitos.at[i, "valor_original"]:
            raise ValueError(f"El valor original de {clave} cambió. Revisa la decisión.")
        if not f.evidencia or f.accion not in {"conservar", "excluir", "corregir"}:
            raise ValueError(f"{clave}: ingresa una acción válida y una evidencia.")
        if f.accion != "corregir" and f.valor_corregido:
            raise ValueError(f"{clave}: valor_corregido solo se usa con corregir.")
        if f.accion == "corregir":
            estado, n, limite = interpretar(f.valor_corregido)
            if estado not in {DETECTADO, IZQUIERDA, DERECHA}:
                raise ValueError(f"{clave}: corrige con un valor positivo o límite explícito en unidad de salida.")
            analitos.loc[i, ["valor_uso", "limite_uso", "estado_uso"]] = [n, limite, estado]
        if f.accion == "excluir":
            analitos.loc[i, ["valor_uso", "limite_uso", "estado_uso"]] = [np.nan, np.nan, "excluido"]
        if f.accion == "conservar" and analitos.at[i, "estado_original"] not in {DETECTADO, IZQUIERDA, DERECHA}:
            raise ValueError(f"{clave}: usa corregir o excluir cuando el resultado original es inválido o falta.")
        analitos.loc[i, ["accion", "evidencia"]] = [f.accion, f.evidencia]

