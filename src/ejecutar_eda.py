"""Ejecuta EDA multielemental, QA/QC y limpieza trazable sobre un archivo CSV."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from analitos import (
    COLUMNAS_DECISION, aplicar_decisiones, cargar_config, marcar_extremos, marcar_motivos, preparar_muestras,
)
from graficos import graficar
from qaqc import DUPLICADOS, revisar_qaqc
from resumen import correlaciones, escribir_csv, exportar_ancha, resumir, sensibilidad_oro


RAIZ = Path(__file__).resolve().parents[1]


def huella(ruta):
    return {"archivo": ruta.name, "sha256": sha256(ruta.read_bytes()).hexdigest()} if ruta else None


def correr(muestras_path, config_path, control_path, decision_path, salida):
    c = cargar_config(config_path)
    muestras, analitos = preparar_muestras(muestras_path, c)
    modelos = marcar_extremos(analitos, c)
    controles = revisar_qaqc(analitos, control_path, c)
    marcar_motivos(analitos)
    aplicar_decisiones(analitos, decision_path)
    cola = analitos.loc[analitos["motivos_revision"].ne("")].copy()
    pendientes = cola.loc[cola["accion"].eq(""), ["muestra_id", "elemento", "valor_original"]]
    plantilla = pendientes.reindex(columns=COLUMNAS_DECISION, fill_value="")
    salida_ancha = exportar_ancha(muestras, analitos, c)
    resumen = resumir(analitos)
    rho, n = correlaciones(analitos, c["muestra_min_detecciones"])
    oro = sensibilidad_oro(analitos)
    duplicados = controles.loc[controles["tipo"].isin(DUPLICADOS)]
    precision = duplicados.groupby(["elemento", "tipo"]).agg(
        n_pares=("control_id", "size"), n_rpd=("rpd_pct", "count"), mediana_rpd_pct=("rpd_pct", "median"),
        n_alerta=("estado", lambda x: x.eq("alerta").sum()),
    ).reset_index()
    registro = {
        "proyecto": c["proyecto"],
        "muestras": len(muestras),
        "elementos": list(c["elementos"]),
        "ensayos": len(analitos),
        "estados_entrada": {str(k): int(v) for k, v in analitos["estado_original"].value_counts().items()},
        "marcas_mad": int(analitos["senal_estadistica"].ne("").sum()),
        "candidatos_revision": len(cola),
        "pendientes_revision": len(plantilla),
        "decisiones_aplicadas": int(analitos["accion"].ne("").sum()),
        "estados_qaqc": {str(k): int(v) for k, v in controles["estado"].value_counts().items()},
        "grupos_elemento_sin_mad": int(modelos["estado"].ne("evaluado").sum()),
        "entradas": {k: huella(p) for k, p in [
            ("muestras", muestras_path), ("configuracion", config_path), ("qaqc", control_path),
            ("decisiones", decision_path),
        ]},
    }
    salida.mkdir(parents=True, exist_ok=True)
    figuras = salida / "figuras"
    figuras.mkdir(exist_ok=True)
    for nombre, tabla in [
        ("analitos_auditados", analitos), ("cola_revision", cola), ("decisiones_plantilla", plantilla),
        ("concentraciones_uso", salida_ancha), ("resumen_elemento_grupo", resumen), ("modelos_mad", modelos),
        ("qaqc_detalle", controles), ("precision_duplicados", precision), ("sensibilidad_oro", oro),
    ]:
        escribir_csv(tabla, salida / f"{nombre}.csv")
    escribir_csv(rho, salida / "correlacion_spearman.csv", indice=True)
    escribir_csv(n, salida / "correlacion_n_pares.csv", indice=True)
    graficar(analitos, rho, n, controles, oro, muestras, c, figuras)
    (salida / "resumen.json").write_text(json.dumps(registro, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(registro, indent=2, ensure_ascii=False))
    return registro


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--muestras", type=Path, help="CSV ancho de ensayos. Por defecto usa las muestras sintéticas.")
    parser.add_argument("--config", type=Path, default=RAIZ / "datos/configuracion.json")
    parser.add_argument("--qaqc", type=Path, help="CSV de QA/QC en unidades de salida.")
    parser.add_argument("--decisiones", type=Path, help="CSV con decisiones documentadas.")
    parser.add_argument("--salida", type=Path, help="Carpeta nueva o dedicada a la corrida.")
    args = parser.parse_args()
    if args.salida is None and (args.muestras or args.decisiones or args.qaqc):
        parser.error("Indica --salida para separar la corrida de los resultados del caso sintético.")
    controles = args.qaqc
    if controles is None and args.muestras is None:
        controles = RAIZ / "datos/controles_sinteticos.csv"
    try:
        correr(
            args.muestras or RAIZ / "datos/muestras_sinteticas.csv", args.config, controles,
            args.decisiones, args.salida or RAIZ / "resultados",
        )
    except (OSError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")


if __name__ == "__main__":
    main()

