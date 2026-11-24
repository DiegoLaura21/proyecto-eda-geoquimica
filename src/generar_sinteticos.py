"""Genera el caso ficticio publicado, con 1.000 muestras y controles separados."""

import argparse
import csv
from pathlib import Path

import numpy as np


RAIZ = Path(__file__).resolve().parents[1]
# LR en la unidad de control. El Au de las muestras se imprime en ppb.
DATOS = {
    "Au": ("Au_ppb", 0.005, 0.32),
    "Ag": ("Ag_ppm", 0.05, 1.4),
    "As": ("As_ppm", 0.5, 45),
    "Sb": ("Sb_ppm", 0.2, 5.5),
    "Cu": ("Cu_ppm", 1, 185),
    "Pb": ("Pb_ppm", 1, 70),
    "Zn": ("Zn_ppm", 1, 155),
    "Mo": ("Mo_ppm", 0.1, 6.5),
    "Fe": ("Fe_pct", 0.01, 4.1),
    "Mn": ("Mn_ppm", 2, 650),
    "Co": ("Co_ppm", 0.2, 17),
    "Ni": ("Ni_ppm", 1, 32),
}


def formato(x):
    return f"{x:.6g}"


def escribir(ruta, filas):
    with ruta.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


def generar(destino):
    rng = np.random.default_rng(41867)
    x, y = rng.uniform([0, 0], [2400, 1700], size=(1000, 2)).T
    dominio = np.select([x < 720, x < 1520], ["Intrusivo", "Corredor silíceo"], default="Volcánico")
    veta = np.exp(-((x - 1160 - 0.15 * (y - 850)) / 210) ** 2)
    factor_veta = 2.1 * veta + rng.normal(0, 0.48, 1000)
    factor_base = rng.normal(0, 0.50, 1000) + 0.6 * (dominio == "Volcánico")
    factor_mafico = rng.normal(0, 0.43, 1000) + 0.65 * (dominio == "Volcánico")
    patrones = {
        "Au": (0.008, 1.95, 0.00, 0.00, 0.72),
        "Ag": (0.14, 1.03, 0.35, 0.00, 0.49),
        "As": (5.4, 1.38, 0.00, 0.00, 0.58),
        "Sb": (0.45, 1.26, 0.00, 0.00, 0.53),
        "Cu": (44, 0.50, 0.81, 0.00, 0.49),
        "Pb": (17, 0.28, 0.93, 0.00, 0.47),
        "Zn": (42, 0.16, 0.95, 0.00, 0.42),
        "Mo": (0.42, 0.28, 0.10, -0.20, 0.69),
        "Fe": (2.8, 0.05, 0.00, 0.46, 0.19),
        "Mn": (340, 0.05, 0.21, 0.45, 0.39),
        "Co": (9, 0.04, 0.05, 0.83, 0.34),
        "Ni": (16, -0.08, 0.10, 0.95, 0.40),
    }
    valores = {
        e: med * np.exp(v * factor_veta + b * factor_base + m * factor_mafico + rng.normal(0, sd, 1000))
        for e, (med, v, b, m, sd) in patrones.items()
    }
    # Pulsos reales simulados de Au grueso. Son valores deliberadamente válidos.
    pepitas = rng.choice(np.flatnonzero(veta > 0.30), size=21, replace=False)
    valores["Au"][pepitas] *= rng.uniform(7, 31, size=len(pepitas))
    # Un caso trazable para el ejercicio de corrección y uno para conservar.
    valores["Au"][127] = 1.25
    valores["Au"][499] = 14.8
    muestras = []
    for i in range(1000):
        lote = f"L{1 + i // 50:02}"
        reg = {
            "muestra_id": f"QB-{i + 1:04}", "lote": lote, "dominio": dominio[i],
            "medio": "roca", "x_local_m": f"{x[i]:.1f}", "y_local_m": f"{y[i]:.1f}",
        }
        for el, (columna, lr, _) in DATOS.items():
            lr *= 2 if lote in {"L07", "L16"} else 1
            escala = 1000 if el == "Au" else 1
            ase = valores[el][i]
            bruto = formato(ase * escala)
            if ase < lr:
                bruto = f"<{formato(lr * escala)}"
            if rng.random() < 0.006:
                bruto = ""
            reg[columna] = bruto
        muestras.append(reg)
    muestras[127]["Au_ppb"] = "125000"
    muestras[499]["Au_ppb"] = "14800"
    muestras[832]["Au_ppb"] = ">10000"
    muestras[876]["Au_ppb"] = "ND"
    muestras[316]["Cu_ppm"] = "123000"
    muestras[500]["Mo_ppm"] = "-9"
    muestras[650]["Ag_ppm"] = "0"
    muestras[750]["Zn_ppm"] = "ver certificado"

    controles = []
    for j in range(20):
        lote = f"L{j + 1:02}"
        comienzo = j * 50
        for el, (columna, ld, referencia) in DATOS.items():
            lr = ld * (2 if lote in {"L07", "L16"} else 1)
            blanco = lr * 28 if (lote, el) in {("L06", "As"), ("L14", "Au")} else None
            crm = referencia * rng.normal(1, 0.035)
            if (lote, el) in {("L08", "Cu"), ("L19", "Zn")}:
                crm = referencia * 1.35
            controles.append(dict(control_id=f"BL-{lote}", lote=lote, elemento=el, tipo="blanco",
                                  muestra_id="", resultado=formato(blanco) if blanco else f"<{formato(lr)}",
                                  limite_reporte=formato(lr), referencia="", tolerancia=""))
            controles.append(dict(control_id=f"CRM-{lote}", lote=lote, elemento=el, tipo="crm",
                                  muestra_id="", resultado=formato(crm), limite_reporte=formato(lr),
                                  referencia=formato(referencia), tolerancia=formato(referencia * 0.12)))
            tipos = [("pulpa", 0.10)] if el != "Au" else [("campo", 0.66), ("rechazo", 0.34), ("pulpa", 0.12)]
            for k, (nivel, sigma) in enumerate(tipos):
                fila = comienzo + 11 + k * 13
                repetido = valores[el][fila] * np.exp(rng.normal(0, sigma))
                controles.append(dict(control_id=f"DU-{nivel}-{lote}", lote=lote, elemento=el,
                                      tipo=f"duplicado_{nivel}", muestra_id=muestras[fila]["muestra_id"],
                                      resultado=formato(repetido) if repetido >= lr else f"<{formato(lr)}",
                                      limite_reporte=formato(lr), referencia="", tolerancia=""))
    decisiones = [
        dict(muestra_id="QB-0128", elemento="Au", valor_original="125000", accion="corregir",
             valor_corregido="1.25", evidencia="Certificado sintético A-0128: 1250 ppb; error de transcripción simulado."),
        dict(muestra_id="QB-0500", elemento="Au", valor_original="14800", accion="conservar",
             valor_corregido="", evidencia="Ejercicio: confirmación simulada del ensayo Au 14.8 ppm y revisión geológica."),
        dict(muestra_id="QB-0501", elemento="Mo", valor_original="-9", accion="excluir",
             valor_corregido="", evidencia="Código negativo inválido simulado; sin concentración verificable."),
    ]
    destino.mkdir(parents=True, exist_ok=True)
    escribir(destino / "muestras_sinteticas.csv", muestras)
    escribir(destino / "controles_sinteticos.csv", controles)
    escribir(destino / "decisiones_ejemplo.csv", decisiones)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, default=RAIZ / "datos")
    generar(parser.parse_args().salida)

