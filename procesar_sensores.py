#!/usr/bin/env python3
"""
procesar_sensores.py

Lee el archivo Excel diario de DATOS (espdesign.com.ar) con columnas:
    Fecha, Dispositivo, Sensor, Valor, Unidad

Y opcionalmente el archivo diario de ALERTAS con columnas:
    Fecha, Nombre, Dispositivo, Sensor, Valor, Unidad

Separa los datos por cada combinación (Dispositivo, Sensor) y genera:
  - Un gráfico PNG individual por sensor (serie temporal), con las alertas
    marcadas como puntos rojos sobre la curva
  - Un dashboard PNG combinado, agrupado por dispositivo
  - Un resumen CSV con estadísticas (min, max, promedio, cantidad de lecturas,
    cantidad de alertas)

Uso:
    python3 procesar_sensores.py datos.xlsx --alertas alertas.xlsx --outdir salida

Pensado para correr diariamente desde GitHub Actions, justo después de que
Playwright descargue los dos archivos del día.
"""

import argparse
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # sin display, para correr en servidores / GitHub Actions
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd


def slugify(texto: str) -> str:
    """Convierte un nombre de dispositivo/sensor en un nombre de archivo seguro."""
    texto = texto.strip().lower()
    texto = re.sub(r"[^\w\s-]", "", texto)
    texto = re.sub(r"[\s]+", "_", texto)
    return texto


def cargar_datos(path_excel: Path) -> pd.DataFrame:
    df = pd.read_excel(path_excel)
    columnas_esperadas = {"Fecha", "Dispositivo", "Sensor", "Valor"}
    faltantes = columnas_esperadas - set(df.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas esperadas en el Excel de datos: {faltantes}")

    df["Fecha"] = pd.to_datetime(df["Fecha"])
    df["Dispositivo"] = df["Dispositivo"].astype(str).str.strip()
    df["Sensor"] = df["Sensor"].astype(str).str.strip()
    df["Etiqueta"] = df["Dispositivo"] + " - " + df["Sensor"]
    df = df.sort_values("Fecha")
    return df


def cargar_alertas(path_excel: Path) -> pd.DataFrame:
    """Carga el archivo de alertas. Devuelve DataFrame vacío con columnas
    correctas si el archivo no tiene filas."""
    df = pd.read_excel(path_excel)
    if df.empty:
        return pd.DataFrame(columns=["Fecha", "Dispositivo", "Sensor", "Valor", "Etiqueta"])

    columnas_esperadas = {"Fecha", "Dispositivo", "Sensor", "Valor"}
    faltantes = columnas_esperadas - set(df.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas esperadas en el Excel de alertas: {faltantes}")

    # El export de alertas viene en formato dd/mm/aaaa HH:MM (día primero)
    df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True)
    df["Dispositivo"] = df["Dispositivo"].astype(str).str.strip()
    df["Sensor"] = df["Sensor"].astype(str).str.strip()
    df["Etiqueta"] = df["Dispositivo"] + " - " + df["Sensor"]
    return df.sort_values("Fecha")


def graficar_sensor_individual(sub_df: pd.DataFrame, etiqueta: str, unidad: str,
                                outdir: Path, alertas_df: pd.DataFrame = None,
                                umbral_alto=None, umbral_bajo=None):
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(sub_df["Fecha"], sub_df["Valor"], color="#2563eb", linewidth=1.2, label="Lecturas", zorder=2)

    if alertas_df is not None and not alertas_df.empty:
        sub_alertas = alertas_df[alertas_df["Etiqueta"] == etiqueta]
        if not sub_alertas.empty:
            ax.scatter(sub_alertas["Fecha"], sub_alertas["Valor"], color="#dc2626",
                       marker="o", s=45, zorder=3, label=f"Alertas ({len(sub_alertas)})")

    if umbral_alto is not None:
        ax.axhline(umbral_alto, color="#f59e0b", linestyle="--", linewidth=1, label=f"Umbral alto ({umbral_alto}{unidad})")
    if umbral_bajo is not None:
        ax.axhline(umbral_bajo, color="#f59e0b", linestyle="--", linewidth=1, label=f"Umbral bajo ({umbral_bajo}{unidad})")

    ax.set_title(etiqueta, fontsize=13, fontweight="bold")
    ax.set_xlabel("Fecha/Hora")
    ax.set_ylabel(f"Valor ({unidad})")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H:%M"))
    fig.autofmt_xdate()
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right", fontsize=8)

    fig.tight_layout()
    nombre_archivo = outdir / f"{slugify(etiqueta)}.png"
    fig.savefig(nombre_archivo, dpi=130)
    plt.close(fig)
    return nombre_archivo


def graficar_dashboard(df: pd.DataFrame, outdir: Path, alertas_df: pd.DataFrame = None):
    etiquetas = sorted(df["Etiqueta"].unique())
    n = len(etiquetas)
    cols = 3
    rows = (n + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 3.5 * rows))
    axes = axes.flatten() if n > 1 else [axes]

    for i, etiqueta in enumerate(etiquetas):
        sub = df[df["Etiqueta"] == etiqueta]
        ax = axes[i]
        ax.plot(sub["Fecha"], sub["Valor"], color="#2563eb", linewidth=1)

        if alertas_df is not None and not alertas_df.empty:
            sub_alertas = alertas_df[alertas_df["Etiqueta"] == etiqueta]
            if not sub_alertas.empty:
                ax.scatter(sub_alertas["Fecha"], sub_alertas["Valor"], color="#dc2626", marker="o", s=20, zorder=3)

        ax.set_title(etiqueta, fontsize=10)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H:%M"))
        ax.tick_params(axis="x", labelrotation=30, labelsize=7)
        ax.tick_params(axis="y", labelsize=8)
        ax.grid(alpha=0.3)

    for j in range(n, len(axes)):
        axes[j].axis("off")

    fig.suptitle("Dashboard de sensores", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    nombre_archivo = outdir / "dashboard_general.png"
    fig.savefig(nombre_archivo, dpi=130)
    plt.close(fig)
    return nombre_archivo


def generar_resumen(df: pd.DataFrame, outdir: Path, alertas_df: pd.DataFrame = None) -> Path:
    resumen = (
        df.groupby("Etiqueta")["Valor"]
        .agg(lecturas="count", minimo="min", maximo="max", promedio="mean")
        .round(2)
        .reset_index()
    )

    if alertas_df is not None and not alertas_df.empty:
        conteo_alertas = alertas_df.groupby("Etiqueta").size().rename("alertas")
        resumen = resumen.merge(conteo_alertas, on="Etiqueta", how="left")
        resumen["alertas"] = resumen["alertas"].fillna(0).astype(int)
    else:
        resumen["alertas"] = 0

    resumen = resumen.sort_values("Etiqueta")
    ruta = outdir / "resumen_sensores.csv"
    resumen.to_csv(ruta, index=False)
    return ruta, resumen


def main():
    parser = argparse.ArgumentParser(description="Procesa datos diarios de sensores + alertas y genera gráficos")
    parser.add_argument("archivo", help="Ruta al archivo Excel de DATOS")
    parser.add_argument("--alertas", default=None, help="Ruta al archivo Excel de ALERTAS (opcional)")
    parser.add_argument("--outdir", default="salida_graficos", help="Carpeta de salida")
    parser.add_argument("--umbral-alto", type=float, default=None, help="Línea de umbral alto en los gráficos individuales")
    parser.add_argument("--umbral-bajo", type=float, default=None, help="Línea de umbral bajo en los gráficos individuales")
    args = parser.parse_args()

    path_excel = Path(args.archivo)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Leyendo datos: {path_excel} ...")
    df = cargar_datos(path_excel)
    print(f"{len(df)} filas cargadas. {df['Etiqueta'].nunique()} sensores detectados.")

    alertas_df = None
    if args.alertas:
        path_alertas = Path(args.alertas)
        print(f"Leyendo alertas: {path_alertas} ...")
        alertas_df = cargar_alertas(path_alertas)
        print(f"{len(alertas_df)} alertas cargadas.")

    for etiqueta in sorted(df["Etiqueta"].unique()):
        sub = df[df["Etiqueta"] == etiqueta]
        unidad = sub["Unidad"].iloc[0] if "Unidad" in sub.columns else ""
        ruta = graficar_sensor_individual(sub, etiqueta, unidad, outdir, alertas_df,
                                           args.umbral_alto, args.umbral_bajo)
        print(f"  -> {ruta.name}")

    ruta_dashboard = graficar_dashboard(df, outdir, alertas_df)
    print(f"Dashboard generado: {ruta_dashboard.name}")

    ruta_resumen, resumen = generar_resumen(df, outdir, alertas_df)
    print(f"Resumen generado: {ruta_resumen.name}")
    print(resumen.to_string(index=False))


if __name__ == "__main__":
    main()
