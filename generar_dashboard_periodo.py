#!/usr/bin/env python3
"""
generar_dashboard_periodo.py

Junta todos los archivos diarios de DATOS (y opcionalmente ALERTAS) acumulados
en una carpeta del repo, y genera un dashboard HTML interactivo (Plotly) para
un período de N días (semanal = 7, mensual = 30).

Convención de nombres esperada (la misma que ya usás):
    sensores_AAAA-MM-DD.xlsx
    alertas_AAAA-MM-DD.xlsx

Uso:
    python3 generar_dashboard_periodo.py \
        --datos-dir data/sensores \
        --alertas-dir data/alertas \
        --dias 7 \
        --outdir docs \
        --nombre-salida reporte_semanal.html

El HTML resultante es autocontenido (usa plotly.js desde CDN) y pensado para
publicarse con GitHub Pages sirviendo la carpeta docs/. Tiene un menú
desplegable para elegir qué sensor mirar, zoom/pan interactivo, y las alertas
marcadas en rojo.
"""

import argparse
import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go


PATRON_FECHA = re.compile(r"(\d{4}-\d{2}-\d{2})")


def extraer_fecha_de_nombre(path: Path):
    m = PATRON_FECHA.search(path.stem)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def listar_archivos_en_rango(directorio: Path, prefijo: str, desde, hasta):
    archivos = []
    if not directorio.exists():
        return archivos
    for f in directorio.glob(f"{prefijo}_*.xlsx"):
        fecha = extraer_fecha_de_nombre(f)
        if fecha and desde <= fecha <= hasta:
            archivos.append((fecha, f))
    archivos.sort(key=lambda x: x[0])
    return archivos


def cargar_datos_periodo(archivos) -> pd.DataFrame:
    dfs = []
    for fecha, f in archivos:
        df = pd.read_excel(f)
        columnas_esperadas = {"Fecha", "Dispositivo", "Sensor", "Valor"}
        if not columnas_esperadas.issubset(df.columns):
            print(f"  ! {f.name}: columnas inesperadas, se omite")
            continue
        df["Fecha"] = pd.to_datetime(df["Fecha"])
        dfs.append(df)
    if not dfs:
        return pd.DataFrame(columns=["Fecha", "Dispositivo", "Sensor", "Valor", "Unidad", "Etiqueta"])
    df = pd.concat(dfs, ignore_index=True)
    df["Dispositivo"] = df["Dispositivo"].astype(str).str.strip()
    df["Sensor"] = df["Sensor"].astype(str).str.strip()
    df["Etiqueta"] = df["Dispositivo"] + " - " + df["Sensor"]
    return df.sort_values("Fecha")


def cargar_alertas_periodo(archivos) -> pd.DataFrame:
    dfs = []
    for fecha, f in archivos:
        df = pd.read_excel(f)
        if df.empty:
            continue
        columnas_esperadas = {"Fecha", "Dispositivo", "Sensor", "Valor"}
        if not columnas_esperadas.issubset(df.columns):
            print(f"  ! {f.name}: columnas inesperadas, se omite")
            continue
        df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True)
        dfs.append(df)
    if not dfs:
        return pd.DataFrame(columns=["Fecha", "Dispositivo", "Sensor", "Valor", "Etiqueta"])
    df = pd.concat(dfs, ignore_index=True)
    df["Dispositivo"] = df["Dispositivo"].astype(str).str.strip()
    df["Sensor"] = df["Sensor"].astype(str).str.strip()
    df["Etiqueta"] = df["Dispositivo"] + " - " + df["Sensor"]
    return df.sort_values("Fecha")


def resamplear(df: pd.DataFrame, regla: str) -> pd.DataFrame:
    """Reduce la cantidad de puntos promediando por ventanas de tiempo,
    para que el HTML no pese demasiado en períodos largos."""
    partes = []
    for etiqueta, sub in df.groupby("Etiqueta"):
        sub = sub.set_index("Fecha").resample(regla)["Valor"].mean().dropna().reset_index()
        sub["Etiqueta"] = etiqueta
        partes.append(sub)
    return pd.concat(partes, ignore_index=True) if partes else df


def construir_dashboard(df: pd.DataFrame, alertas_df: pd.DataFrame, titulo: str) -> go.Figure:
    etiquetas = sorted(df["Etiqueta"].unique())
    fig = go.Figure()

    for i, etiqueta in enumerate(etiquetas):
        sub = df[df["Etiqueta"] == etiqueta]
        fig.add_trace(go.Scatter(
            x=sub["Fecha"], y=sub["Valor"], mode="lines", name=etiqueta,
            visible=(i == 0), line=dict(color="#2563eb", width=1.5),
        ))

        sub_alertas = alertas_df[alertas_df["Etiqueta"] == etiqueta] if not alertas_df.empty else alertas_df
        fig.add_trace(go.Scatter(
            x=sub_alertas["Fecha"] if not sub_alertas.empty else [],
            y=sub_alertas["Valor"] if not sub_alertas.empty else [],
            mode="markers", name=f"Alertas: {etiqueta}",
            marker=dict(color="#dc2626", size=8, symbol="circle"),
            visible=(i == 0), showlegend=False,
        ))

    # Cada sensor ocupa 2 trazas (curva + alertas); el menú prende solo el par correspondiente
    botones = []
    for i, etiqueta in enumerate(etiquetas):
        visibilidad = [False] * (len(etiquetas) * 2)
        visibilidad[i * 2] = True
        visibilidad[i * 2 + 1] = True
        botones.append(dict(label=etiqueta, method="update",
                             args=[{"visible": visibilidad}, {"title": f"{titulo} — {etiqueta}"}]))

    fig.update_layout(
        title=f"{titulo} — {etiquetas[0]}" if etiquetas else titulo,
        updatemenus=[dict(active=0, buttons=botones, x=0, y=1.15, xanchor="left")],
        xaxis_title="Fecha", yaxis_title="Valor (°C)",
        template="plotly_white", height=550,
        margin=dict(t=110),
    )
    return fig


def main():
    parser = argparse.ArgumentParser(description="Genera dashboard HTML semanal/mensual de sensores")
    parser.add_argument("--datos-dir", required=True, help="Carpeta con los xlsx diarios de datos")
    parser.add_argument("--alertas-dir", default=None, help="Carpeta con los xlsx diarios de alertas")
    parser.add_argument("--dias", type=int, default=7, help="Cantidad de días hacia atrás a incluir (7=semanal, 30=mensual)")
    parser.add_argument("--hasta", default=None, help="Fecha final AAAA-MM-DD (default: hoy)")
    parser.add_argument("--outdir", default="docs", help="Carpeta de salida (para GitHub Pages)")
    parser.add_argument("--nombre-salida", default=None, help="Nombre del archivo HTML de salida")
    args = parser.parse_args()

    hasta = datetime.strptime(args.hasta, "%Y-%m-%d").date() if args.hasta else datetime.now().date()
    desde = hasta - timedelta(days=args.dias - 1)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Buscando archivos de datos entre {desde} y {hasta} ...")
    archivos_datos = listar_archivos_en_rango(Path(args.datos_dir), "sensores", desde, hasta)
    print(f"  {len(archivos_datos)} archivos de datos encontrados")
    df = cargar_datos_periodo(archivos_datos)

    alertas_df = pd.DataFrame(columns=["Fecha", "Dispositivo", "Sensor", "Valor", "Etiqueta"])
    if args.alertas_dir:
        archivos_alertas = listar_archivos_en_rango(Path(args.alertas_dir), "alertas", desde, hasta)
        print(f"  {len(archivos_alertas)} archivos de alertas encontrados")
        alertas_df = cargar_alertas_periodo(archivos_alertas)

    if df.empty:
        print("No se encontraron datos en el rango solicitado. No se genera el HTML.")
        return

    # Reducir resolución para que el archivo no pese demasiado
    regla = "15min" if args.dias <= 10 else "1h"
    print(f"Resampleando datos cada {regla} ({len(df)} filas originales) ...")
    df_resampleado = resamplear(df, regla)
    print(f"  {len(df_resampleado)} filas tras resamplear")

    periodo_txt = "Vista semanal" if args.dias <= 10 else "Vista mensual"
    titulo = f"{periodo_txt} de sensores ({desde.strftime('%d/%m')} — {hasta.strftime('%d/%m/%Y')})"
    fig = construir_dashboard(df_resampleado, alertas_df, titulo)

    nombre_salida = args.nombre_salida or ("reporte_semanal.html" if args.dias <= 10 else "reporte_mensual.html")
    ruta_salida = outdir / nombre_salida
    fig.write_html(ruta_salida, include_plotlyjs="cdn")
    print(f"Dashboard generado: {ruta_salida}")


if __name__ == "__main__":
    main()
