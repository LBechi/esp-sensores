"""
Consolida los archivos diarios de datos/ y alertas/ correspondientes a un
mes y año en un único archivo (xlsx o csv) por categoría.

Uso:
    python consolidar_mensual.py                     # consolida el mes anterior
    python consolidar_mensual.py --anio 2026 --mes 8  # consolida agosto 2026
    python consolidar_mensual.py --formato csv        # salida en CSV en vez de xlsx
"""

import argparse
import glob
import os
import sys
from datetime import date, timedelta

import pandas as pd


def mes_anterior():
    hoy = date.today()
    primero_este_mes = hoy.replace(day=1)
    ultimo_dia_mes_pasado = primero_este_mes - timedelta(days=1)
    return ultimo_dia_mes_pasado.year, ultimo_dia_mes_pasado.month


def consolidar(carpeta_origen, prefijo, anio, mes, carpeta_salida, formato):
    patron = os.path.join(carpeta_origen, f"{prefijo}_{anio}-{mes:02d}-*.xlsx")
    archivos = sorted(glob.glob(patron))

    if not archivos:
        print(f"[{prefijo}] No se encontraron archivos para {anio}-{mes:02d} "
              f"(patrón: {patron})")
        return False

    dfs = []
    for archivo in archivos:
        try:
            dfs.append(pd.read_excel(archivo))
        except Exception as e:
            print(f"[{prefijo}] Error leyendo {archivo}: {e}")
            return False

    combinado = pd.concat(dfs, ignore_index=True)

    os.makedirs(carpeta_salida, exist_ok=True)
    salida = os.path.join(carpeta_salida, f"{prefijo}_{anio}-{mes:02d}.{formato}")

    if formato == "csv":
        combinado.to_csv(salida, index=False)
    else:
        combinado.to_excel(salida, index=False)

    print(f"[{prefijo}] {len(archivos)} archivos combinados -> {salida} "
          f"({len(combinado)} filas)")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--anio", type=int, default=None)
    parser.add_argument("--mes", type=int, default=None)
    parser.add_argument("--formato", choices=["xlsx", "csv"], default="xlsx")
    args = parser.parse_args()

    if args.anio and args.mes:
        anio, mes = args.anio, args.mes
    else:
        anio, mes = mes_anterior()

    print(f"Consolidando periodo {anio}-{mes:02d} (formato: {args.formato})")

    ok_datos = consolidar("datos", "sensores", anio, mes, "datos_mensuales", args.formato)
    ok_alertas = consolidar("alertas", "alertas", anio, mes, "alertas_mensuales", args.formato)

    if not ok_datos or not ok_alertas:
        print("El consolidado terminó con errores o sin datos para alguna categoría.")
        sys.exit(1)

    print("Consolidado mensual completado con éxito.")
