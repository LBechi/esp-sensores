"""
Borra del repositorio los archivos diarios (datos/ y alertas/) y el
consolidado mensual (datos_mensuales/ y alertas_mensuales/) correspondientes
a un mes y año particular. Pensado para ejecutarse manualmente
(workflow_dispatch), nunca de forma automática/programada.

Uso:
    python borrar_mes.py --anio 2026 --mes 8
"""

import argparse
import glob
import os


def borrar_diarios(carpeta, prefijo, anio, mes):
    patron = os.path.join(carpeta, f"{prefijo}_{anio}-{mes:02d}-*.xlsx")
    archivos = sorted(glob.glob(patron))
    for archivo in archivos:
        os.remove(archivo)
        print(f"Borrado: {archivo}")
    return len(archivos)


def borrar_mensual(carpeta, prefijo, anio, mes):
    borrados = 0
    for formato in ("xlsx", "csv"):
        archivo = os.path.join(carpeta, f"{prefijo}_{anio}-{mes:02d}.{formato}")
        if os.path.exists(archivo):
            os.remove(archivo)
            print(f"Borrado: {archivo}")
            borrados += 1
    return borrados


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--anio", type=int, required=True)
    parser.add_argument("--mes", type=int, required=True)
    args = parser.parse_args()

    anio, mes = args.anio, args.mes
    print(f"Borrando registros de {anio}-{mes:02d}...")

    total = 0
    total += borrar_diarios("datos", "sensores", anio, mes)
    total += borrar_diarios("alertas", "alertas", anio, mes)
    total += borrar_mensual("datos_mensuales", "sensores", anio, mes)
    total += borrar_mensual("alertas_mensuales", "alertas", anio, mes)

    print(f"Total de archivos borrados: {total} ({anio}-{mes:02d})")
