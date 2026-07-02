import asyncio
import os
import json
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ─── Variables de entorno (cargadas desde GitHub Secrets) ───────────────────
USERNAME    = os.environ["ESP_USERNAME"]
PASSWORD    = os.environ["ESP_PASSWORD"]
CREDENTIALS = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
FOLDER_ID   = os.environ["GOOGLE_DRIVE_FOLDER_ID"]

LOGIN_URL = "https://espdesign.com.ar/#!/login"
LOG_URL   = "https://espdesign.com.ar/#!/log"

# ─── Descarga del Excel desde el panel ──────────────────────────────────────
async def download_excel() -> str:
    yesterday  = datetime.now() - timedelta(days=1)
    date_str   = yesterday.strftime("%d/%m/%Y")   # formato del panel
    filename   = f"sensores_{yesterday.strftime('%Y-%m-%d')}.xlsx"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx     = await browser.new_context(accept_downloads=True)
        page    = await ctx.new_page()

        # 1. Login
        await page.goto(LOGIN_URL)
        await page.wait_for_load_state("networkidle")

        await page.fill(
            'input[type="email"], input[name="email"], '
            'input[placeholder*="mail" i], input[placeholder*="usuario" i]',
            USERNAME
        )
        await page.fill('input[type="password"]', PASSWORD)
        await page.click(
            'button[type="submit"], button:has-text("Ingresar"), '
            'button:has-text("Login"), button:has-text("Entrar")'
        )
        await page.wait_for_load_state("networkidle")

        # 2. Ir al Data Logger
        await page.goto(LOG_URL)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)   # esperar renderizado Angular

        # 3. Completar fechas (inicio y fin = ayer)
        date_inputs = await page.query_selector_all('input[type="text"]')
        if len(date_inputs) >= 2:
            await date_inputs[0].triple_click()
            await date_inputs[0].type(date_str)
            await date_inputs[1].triple_click()
            await date_inputs[1].type(date_str)

        # 4. Aplicar filtro
        await page.click('button:has-text("Aplicar")')
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        # 5. Exportar y capturar descarga
        async with page.expect_download(timeout=30000) as dl_info:
            await page.click('button:has-text("Exportar")')
        download = await dl_info.value
        await download.save_as(filename)

        await browser.close()
        print(f"✅ Archivo descargado: {filename}")
        return filename

# ─── Subida a Google Drive ───────────────────────────────────────────────────
def upload_to_drive(filename: str) -> None:
    creds = service_account.Credentials.from_service_account_info(
        CREDENTIALS,
        scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    service = build("drive", "v3", credentials=creds)

    meta  = {"name": filename, "parents": [FOLDER_ID]}
    media = MediaFileUpload(
        filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    f = service.files().create(body=meta, media_body=media, fields="id").execute()
    print(f"✅ Subido a Drive  →  ID: {f.get('id')}")

# ─── Main ────────────────────────────────────────────────────────────────────
async def main():
    print(f"⏰ Corriendo para fecha: {(datetime.now()-timedelta(days=1)).strftime('%Y-%m-%d')}")
    filename = await download_excel()
    upload_to_drive(filename)
    print("🎉 ¡Proceso completado!")

if __name__ == "__main__":
    asyncio.run(main())
