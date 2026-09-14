"""
Sube (o reemplaza) en una carpeta de Google Drive los archivos mensuales
consolidados de datos_mensuales/ y alertas_mensuales/.

Requiere las variables de entorno:
    GDRIVE_SA_KEY_JSON  -> contenido completo del JSON de la cuenta de servicio
    GDRIVE_FOLDER_ID    -> ID de la carpeta de Drive destino

Uso:
    python subir_drive.py                     # sube el mes anterior
    python subir_drive.py --anio 2026 --mes 8 --formato xlsx
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def mes_anterior():
    hoy = date.today()
    primero_este_mes = hoy.replace(day=1)
    ultimo_dia_mes_pasado = primero_este_mes - timedelta(days=1)
    return ultimo_dia_mes_pasado.year, ultimo_dia_mes_pasado.month


def get_drive_service():
    info = json.loads(os.environ["GDRIVE_SA_KEY_JSON"])
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)


def subir_o_reemplazar(service, folder_id, ruta_local, nombre_remoto):
    if not os.path.exists(ruta_local):
        print(f"No existe {ruta_local}, se omite.")
        return False

    query = f"name = '{nombre_remoto}' and '{folder_id}' in parents and trashed = false"
    resultados = service.files().list(q=query, fields="files(id)").execute()
    archivos = resultados.get("files", [])

    media = MediaFileUpload(ruta_local, resumable=True)

    if archivos:
        file_id = archivos[0]["id"]
        service.files().update(fileId=file_id, media_body=media).execute()
        print(f"Reemplazado en Drive: {nombre_remoto}")
    else:
        metadata = {"name": nombre_remoto, "parents": [folder_id]}
        service.files().create(body=metadata, media_body=media, fields="id").execute()
        print(f"Subido a Drive: {nombre_remoto}")

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

    folder_id = os.environ["GDRIVE_FOLDER_ID"]
    service = get_drive_service()

    ok1 = subir_o_reemplazar(
        service, folder_id,
        f"datos_mensuales/sensores_{anio}-{mes:02d}.{args.formato}",
        f"sensores_{anio}-{mes:02d}.{args.formato}",
    )
    ok2 = subir_o_reemplazar(
        service, folder_id,
        f"alertas_mensuales/alertas_{anio}-{mes:02d}.{args.formato}",
        f"alertas_{anio}-{mes:02d}.{args.formato}",
    )

    if not ok1 or not ok2:
        sys.exit(1)

    print("Subida a Drive completada.")
