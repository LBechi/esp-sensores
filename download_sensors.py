import asyncio
import os
import json
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

USERNAME    = os.environ["ESP_USERNAME"]
PASSWORD    = os.environ["ESP_PASSWORD"]
CREDENTIALS = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
FOLDER_ID   = os.environ["GOOGLE_DRIVE_FOLDER_ID"]

LOGIN_URL = "https://espdesign.com.ar/#!/login"
LOG_URL   = "https://espdesign.com.ar/#!/log"

async def download_excel() -> str:
    yesterday = datetime.now() - timedelta(days=1)
    date_str  = yesterday.strftime("%d/%m/%Y")
    filename  = f"sensores_{yesterday.strftime('%Y-%m-%d')}.xlsx"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx     = await browser.new_context(accept_downloads=True)
        page    = await ctx.new_page()

        # 1. Login
        print("Navegando al login...")
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path="01_login.png")

        await page.fill('input[type="email"], input[name="email"], input[type="text"]', USERNAME)
        await page.fill('input[type="password"]', PASSWORD)
        await page.screenshot(path="02_credenciales.png")

        await page.click('button[type="submit"], button:has-text("Ingresar"), button:has-text("Login")')
        await page.wait_for_timeout(5000)
        await page.screenshot(path="03_post_login.png")
        print(f"URL tras login: {page.url}")

        # 2. Navegar al log
        print("Navegando al Data Logger...")
        await page.goto(LOG_URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)
        await page.screenshot(path="04_datalogger.png")
        print(f"URL actual: {page.url}")

        # 3. Esperar tabla de datos
        print("Esperando que cargue la tabla...")
        await page.wait_for_selector("table, tr, .table", timeout=30000)
        await page.wait_for_timeout(2000)
        await page.screenshot(path="05_tabla_cargada.png")

        # 4. Completar fechas
        print(f"Cargando fecha: {date_str}")
        date_inputs = await page.query_selector_all('input[type="text"]')
        print(f"  Inputs de texto encontrados: {len(date_inputs)}")
        if len(date_inputs) >= 2:
            await date_inputs[0].triple_click()
            await date_inputs[0].type(date_str, delay=50)
            await page.wait_for_timeout(500)
            await date_inputs[1].triple_click()
            await date_inputs[1].type(date_str, delay=50)
            await page.wait_for_timeout(500)
        await page.screenshot(path="06_fechas.png")

        # 5. Click Aplicar
        print("Haciendo click en Aplicar...")
        aplicar = page.locator("button", has_text="Aplicar").first
        await aplicar.wait_for(timeout=15000)
        await aplicar.click()
        await page.wait_for_timeout(5000)
        await page.screenshot(path="07_post_aplicar.png")

        # 6. Exportar
        print("Exportando...")
        async with page.expect_download(timeout=30000) as dl_info:
            exportar = page.locator("button", has_text="Exportar").first
            await exportar.click()
        download = await dl_info.value
        await download.save_as(filename)
        await browser.close()
        print(f"✅ Descargado: {filename}")
        return filename

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
    print(f"✅ Subido a Drive → ID: {f.get('id')}")

async def main():
    filename = await download_excel()
    upload_to_drive(filename)
    print("🎉 ¡Proceso completado!")

if __name__ == "__main__":
    asyncio.run(main())
