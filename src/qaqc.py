"""Controles analíticos de blancos, CRM y duplicados por elemento."""

import numpy as np
import pandas as pd

from analitos import DETECTADO, DERECHA, IZQUIERDA, factor_unidad, interpretar, leer_csv


DUPLICADOS = {"duplicado_campo", "duplicado_rechazo", "duplicado_pulpa"}
TIPOS = DUPLICADOS | {"blanco", "crm"}
ENTRADA = [
    "control_id", "lote", "elemento", "tipo", "muestra_id", "resultado",
    "limite_reporte", "referencia", "tolerancia",
]


def exigir_numero(valor, campo, control, *, opcional=False):
    if opcional and not valor.strip():
        return None
    estado, n, _ = interpretar(valor)
    if estado != DETECTADO:
        raise ValueError(f"{control}: {campo} requiere un valor positivo en unidad de salida.")
    return n


def evaluar_control(f, regla, lr, origen):
    estado, valor, limite = interpretar(f.resultado, lr)
    base = {"valor_control": valor, "limite_control": limite, "lr_qaqc": lr,
            "estado_control": estado, "valor_primario": np.nan, "rpd_pct": np.nan,
            "referencia_evaluada": np.nan, "tolerancia_evaluada": np.nan}
    if f.tipo == "blanco":
        if lr is None:
            return base, "revisar", "falta_lr_para_blanco"
        maximo = regla["blanco_max_en_lr"] * lr
        base["tolerancia_evaluada"] = maximo
        if estado == DETECTADO:
            return (base, "alerta", "blanco_sobre_maximo") if valor > maximo else (base, "ok", "blanco_en_limite")
        if estado == IZQUIERDA and limite <= maximo:
            return base, "ok", "blanco_bajo_maximo"
        if estado == DERECHA and limite >= maximo:
            return base, "alerta", "blanco_sobre_maximo"
        return base, "revisar", "blanco_no_evaluable"
    if f.tipo == "crm":
        centro = exigir_numero(f.referencia, "referencia", f.control_id)
        ancho = exigir_numero(f.tolerancia, "tolerancia", f.control_id)
        base.update(referencia_evaluada=centro, tolerancia_evaluada=ancho)
        if estado != DETECTADO:
            return base, "revisar", "crm_no_cuantificado"
        return (base, "alerta", "crm_fuera_rango") if abs(valor - centro) > ancho else (base, "ok", "crm_en_rango")

    primario = origen.loc[(f.muestra_id, f.elemento)]
    a = primario["valor_original_num"]
    base["valor_primario"] = a
    if lr is None:
        return base, "revisar", "falta_lr_para_duplicado"
    if estado != DETECTADO or primario["estado_original"] != DETECTADO:
        return base, "revisar", "par_censurado_o_invalido"
    if min(a, valor) < regla["duplicado_min_en_lr"] * lr:
        return base, "revisar", "par_cercano_lr"
    # Cociente reescalado para evitar desbordamiento con concentraciones muy altas.
    cociente = min(a, valor) / max(a, valor)
    rpd = 200 * (1 - cociente) / (1 + cociente)
    base["rpd_pct"] = rpd
    base["tolerancia_evaluada"] = regla["rpd_max_pct"]
    return (base, "alerta", "rpd_alto") if rpd > regla["rpd_max_pct"] else (base, "ok", "rpd_en_rango")


def revisar_qaqc(analitos, ruta, config):
    analitos["qaqc_lote"] = "sin_control"
    analitos["qaqc_muestra"] = "sin_control"
    columnas = ENTRADA + [
        "unidad", "estado_control", "valor_control", "limite_control", "lr_qaqc",
        "valor_primario", "rpd_pct", "referencia_evaluada", "tolerancia_evaluada", "estado", "motivo",
    ]
    if ruta is None:
        return pd.DataFrame(columns=columnas)
    controles = leer_csv(ruta, ENTRADA)[ENTRADA]
    controles = controles.apply(lambda col: col.str.strip())
    if controles["control_id"].eq("").any() or controles.duplicated(["control_id", "elemento"]).any():
        raise ValueError("QA/QC: los controles requieren ID y una fila por ID y elemento.")
    origen = analitos.set_index(["muestra_id", "elemento"])
    lotes = set(analitos["lote"])
    filas = []
    for f in controles.itertuples(index=False):
        if f.tipo not in TIPOS or f.elemento not in config["elementos"] or f.lote not in lotes:
            raise ValueError(f"{f.control_id}: verifica tipo, elemento y lote de QA/QC.")
        if f.tipo in DUPLICADOS:
            clave = (f.muestra_id, f.elemento)
            if clave not in origen.index or origen.loc[clave, "lote"] != f.lote:
                raise ValueError(f"{f.control_id}: el duplicado requiere una muestra primaria del mismo lote.")
        elif f.muestra_id:
            raise ValueError(f"{f.control_id}: muestra_id solo se usa en duplicados.")
        regla = config["elementos"][f.elemento]
        lr = exigir_numero(f.limite_reporte, "limite_reporte", f.control_id, opcional=True)
        if lr is None and regla.get("limite_reporte") is not None:
            lr = regla["limite_reporte"] * factor_unidad(regla)
        base, estado, motivo = evaluar_control(f, config["qaqc"], lr, origen)
        filas.append({**f._asdict(), **base, "unidad": regla["unidad_salida"], "estado": estado, "motivo": motivo})
    resultado = pd.DataFrame(filas, columns=columnas)
    prioridad = {"ok": 1, "revisar": 2, "alerta": 3}
    grupos = [
        (~resultado["tipo"].isin(DUPLICADOS), ["lote", "elemento"], "qaqc_lote"),
        (resultado["tipo"].isin(DUPLICADOS), ["muestra_id", "elemento"], "qaqc_muestra"),
    ]
    for filtro, claves, destino in grupos:
        rangos = resultado.loc[filtro, [*claves, "estado"]].assign(
            rango=lambda x: x["estado"].map(prioridad)
        ).groupby(claves)["rango"].max()
        asignacion = rangos.reindex(pd.MultiIndex.from_frame(analitos[claves]))
        por_rango = {v: k for k, v in prioridad.items()}
        analitos[destino] = asignacion.map(por_rango).fillna("sin_control").to_numpy()
    return resultado

