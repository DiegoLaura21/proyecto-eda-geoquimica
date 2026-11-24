"""Figuras para revisar distribuciones, correlación, calidad y oro."""

from math import ceil

import matplotlib
matplotlib.use("Agg")
from matplotlib.colors import LogNorm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analitos import DETECTADO, IZQUIERDA


TINTA = "#243b38"
VERDE = "#287b67"
ORO = "#bb7c23"
ROJO = "#b4453c"
PALETA = ["#226d88", "#bd7527", "#47845d", "#795b99", "#8d5943", "#415e75"]
NIVELES = {"duplicado_campo": "Campo", "duplicado_rechazo": "Rechazo", "duplicado_pulpa": "Pulpa"}


def estilo():
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10, "figure.facecolor": "#f2f5f2",
        "axes.facecolor": "white", "axes.labelcolor": TINTA, "axes.titlecolor": TINTA,
        "text.color": TINTA, "axes.edgecolor": "#b9c8c1", "axes.spines.top": False,
        "axes.spines.right": False, "grid.color": "#e0e9e3", "axes.axisbelow": True,
        "legend.frameon": False, "savefig.dpi": 150,
    })


def titular(fig, titulo, nota):
    fig.suptitle(titulo, x=0.075, y=0.975, ha="left", fontsize=23, fontweight="bold")
    fig.text(0.077, 0.925, nota, color="#4a645d", va="top")


def guardar(fig, ruta):
    fig.savefig(ruta, facecolor=fig.get_facecolor())
    plt.close(fig)


def distribuciones(analitos, destino):
    elementos = analitos["elemento"].unique()
    for pagina, inicio in enumerate(range(0, len(elementos), 12), start=1):
        sub = elementos[inicio:inicio + 12]
        filas = ceil(len(sub) / 3)
        fig, ejes = plt.subplots(filas, 3, figsize=(12.4, max(6.6, 2.15 * filas + 1.8)), squeeze=False)
        fig.subplots_adjust(left=0.075, right=0.96, bottom=0.10, top=0.85, wspace=0.30, hspace=0.74)
        titular(fig, "Distribuciones multielementales",
                "Histogramas de log₁₀ concentración cuantificada · las censuras se informan aparte")
        for ax, el in zip(ejes.flat, sub):
            datos = analitos.loc[analitos["elemento"].eq(el)]
            detectados = datos.loc[datos["estado_uso"].eq(DETECTADO)]
            x = np.log10(detectados["valor_uso"])
            censura = 100 * datos["estado_uso"].eq(IZQUIERDA).mean()
            ax.set_title(f"{el} ({datos['unidad'].iat[0]}) · n={len(x)} · {censura:.1f}% <LR", loc="left", fontsize=10)
            if len(x):
                ax.hist(x, bins="auto" if len(x) <= 30 else 24, color=VERDE, alpha=0.83)
                extremos = detectados.loc[detectados["senal_estadistica"].ne("") & detectados["accion"].eq("")]
                ax.plot(np.log10(extremos["valor_uso"]), np.zeros(len(extremos)), "|",
                        color=ROJO, markersize=9, markeredgewidth=1.4, clip_on=False)
            else:
                ax.text(0.5, 0.5, "Sin cuantificados", ha="center", transform=ax.transAxes)
            ax.grid(axis="y", linewidth=0.7)
            ax.tick_params(labelsize=8)
        for ax in list(ejes.flat)[len(sub):]:
            ax.set_visible(False)
        fig.text(0.075, 0.045, "Marcas rojas · extremos de la revisión original todavía pendientes", color=ROJO)
        nombre = "01_distribuciones.png" if pagina == 1 else f"01_distribuciones_{pagina:02}.png"
        guardar(fig, destino / nombre)


def correlacion(matriz, n, destino):
    numero = len(matriz)
    lado = max(7, min(numero * 0.55 + 3, 16))
    fig, ax = plt.subplots(figsize=(lado + 1, lado))
    fig.subplots_adjust(left=0.12, right=0.84, bottom=0.12, top=0.85)
    titular(fig, "Asociaciones multielementales", "Spearman sobre muestras cuantificadas en ambos elementos")
    cmap = matplotlib.colormaps["RdBu_r"].copy()
    cmap.set_bad("#e8ece8")
    imagen = ax.imshow(matriz.to_numpy(), cmap=cmap, vmin=-1, vmax=1)
    ax.set_xticks(np.arange(numero), matriz.columns)
    ax.set_yticks(np.arange(numero), matriz.index)
    if numero <= 14:
        for i in range(numero):
            for j in range(numero):
                v = matriz.iat[i, j]
                if np.isfinite(v):
                    ax.text(j, i, f"{round(v, 2) + 0.0:.2f}", ha="center", va="center",
                            color="white" if abs(v) > 0.55 else TINTA, fontsize=8)
    fig.colorbar(imagen, ax=ax, shrink=0.83, label="Coeficiente ρ")
    pares = n.to_numpy()[np.triu_indices(numero, k=1)] if numero > 1 else n.to_numpy().ravel()
    fig.text(0.075, 0.045, f"Máximo de muestras por par: {pares.max()} · revisa n por par y mezcla de dominios")
    guardar(fig, destino / "02_correlacion.png")


def calidad(analitos, destino):
    elementos = analitos["elemento"].unique()
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(12, max(6.0, min(13, len(elementos) * 0.39 + 2))))
    fig.subplots_adjust(left=0.09, right=0.96, bottom=0.16, top=0.84, wspace=0.28)
    titular(fig, "Disponibilidad y señales de revisión", "Una señal orienta la revisión del ensayo · los motivos pueden coincidir")
    n = analitos.groupby("elemento")["muestra_id"].size().reindex(elementos)
    p = np.arange(len(elementos))
    base = np.zeros(len(n))
    for etiqueta, seleccion, color in [
        ("Detectado", analitos["estado_uso"].eq(DETECTADO), VERDE),
        ("Bajo LR", analitos["estado_uso"].eq(IZQUIERDA), "#85aaae"),
        ("Restantes", ~analitos["estado_uso"].isin([DETECTADO, IZQUIERDA]), "#dbad70"),
    ]:
        valores = 100 * seleccion.groupby(analitos["elemento"]).sum().reindex(elementos) / n
        ax.barh(p, valores, left=base, color=color, label=etiqueta)
        base += valores
    motivos = analitos["motivos_revision"].ne("") & analitos["accion"].eq("")
    estadistica = analitos["senal_estadistica"].ne("") & analitos["accion"].eq("")
    for etiqueta, seleccion, offset, color in [
        ("Cualquier motivo", motivos, -0.19, "#58768e"), ("Marca MAD", estadistica, 0.19, ROJO)
    ]:
        valores = seleccion.groupby(analitos["elemento"]).sum().reindex(elementos)
        bx.barh(p + offset, valores, height=0.34, color=color, label=etiqueta)
    for eje in (ax, bx):
        eje.set_yticks(p, elementos)
        eje.invert_yaxis()
        eje.grid(axis="x")
        eje.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncols=3)
    ax.set_xlabel("Porcentaje de ensayos")
    bx.set_xlabel("Ensayos pendientes de revisión")
    guardar(fig, destino / "03_calidad.png")


def panel_oro(analitos, controles, sensibilidad, muestras, config, destino):
    oro = analitos.loc[analitos["elemento"].eq("Au")]
    if oro.empty:
        return
    detectados = oro.loc[oro["estado_uso"].eq(DETECTADO)]
    unidad = oro["unidad"].iat[0]
    fig, ejes = plt.subplots(2, 2, figsize=(13.0, 8.8))
    fig.subplots_adjust(left=0.084, right=0.94, bottom=0.095, top=0.845, hspace=0.57, wspace=0.34)
    titular(fig, "Oro · cómo examinar la cola alta",
            "Distribución por dominio, precisión según el tipo de duplicado y ubicación en la malla de muestreo")
    ax, bx, cx, dx = ejes.flat
    for i, (grupo, datos) in enumerate(detectados.groupby("grupo", sort=False)):
        valores = np.sort(datos["valor_uso"])
        ax.step(valores, 100 * np.arange(1, len(valores) + 1) / len(valores), where="post",
                color=PALETA[i % len(PALETA)], label=f"{grupo} ({len(valores)})")
    ax.set(title="Distribución de detectados por grupo", xlabel=f"Au ({unidad}, escala log)", ylabel="Detectados acumulados (%)")
    if not detectados.empty:
        ax.set_xscale("log")
        ax.legend(loc="lower right", fontsize=8)
    else:
        ax.text(0.5, 0.5, "Sin Au cuantificado", ha="center", transform=ax.transAxes)

    pares = controles.loc[controles["elemento"].eq("Au") & controles["rpd_pct"].notna()]
    for i, (tipo, datos) in enumerate(pares.groupby("tipo", sort=False)):
        bx.scatter(datos["valor_primario"], datos["valor_control"], s=27, alpha=0.72,
                   color=PALETA[i % len(PALETA)], label=f"{NIVELES[tipo]} ({len(datos)})")
    if not pares.empty:
        limites = pares[["valor_primario", "valor_control"]].to_numpy()
        minimo, maximo = limites.min() / 1.15, limites.max() * 1.15
        bx.plot([minimo, maximo], [minimo, maximo], "--", color="#6f8178", linewidth=1)
        bx.set(xscale="log", yscale="log", xlim=(minimo, maximo), ylim=(minimo, maximo))
        bx.legend(loc="upper left", fontsize=8)
    else:
        bx.text(0.5, 0.5, "Sin pares evaluables por RPD", ha="center", transform=bx.transAxes)
    bx.set(title="Duplicados elegibles y línea 1:1", xlabel=f"Primario ({unidad})", ylabel=f"Duplicado ({unidad})")

    if not sensibilidad.empty:
        y = np.arange(len(sensibilidad))
        cx.barh(y, sensibilidad["pct_suma_concentraciones_en_cola"], color=ORO)
        cx.set_yticks(y, sensibilidad["grupo"], fontsize=8)
        cx.invert_yaxis()
    cx.set(title="Influencia del 1 % superior de detectados", xlabel="% de la suma de concentraciones", xlim=(0, 100))
    coords = config.get("columnas_coordenadas")
    if coords and not detectados.empty:
        posiciones = muestras.set_index(config["columna_id"])[coords].apply(pd.to_numeric, errors="coerce")
        posiciones = posiciones.reindex(detectados["muestra_id"])
        valido = np.isfinite(posiciones).all(axis=1).to_numpy()
        ubicados = detectados.loc[valido, "valor_uso"]
    else:
        ubicados = pd.Series(dtype=float)
    if len(ubicados):
        mapa = dx.scatter(posiciones.iloc[valido, 0], posiciones.iloc[valido, 1], c=ubicados, s=13,
                          cmap="viridis", norm=LogNorm(), alpha=0.82)
        fig.colorbar(mapa, ax=dx, label=f"Au ({unidad})")
        dx.set(title="Distribución espacial de detectados", xlabel=coords[0], ylabel=coords[1], aspect="equal")
    else:
        dx.text(0.5, 0.5, "Sin coordenadas utilizables", ha="center", transform=dx.transAxes)
        dx.set_axis_off()
    for eje in (ax, bx, cx):
        eje.grid(linewidth=0.65)
    guardar(fig, destino / "04_oro.png")


def graficar(analitos, matriz, pares, controles, sensibilidad, muestras, config, destino):
    estilo()
    distribuciones(analitos, destino)
    correlacion(matriz, pares, destino)
    calidad(analitos, destino)
    panel_oro(analitos, controles, sensibilidad, muestras, config, destino)

