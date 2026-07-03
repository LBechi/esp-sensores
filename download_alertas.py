import asyncio
import os
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

USERNAME = os.environ["ESP_USERNAME"]
PASSWORD = os.environ["ESP_PASSWORD"]

LOGIN_URL = "https://espdesign.com.ar/#!/login"

async def download_alertas() -> str:
    yesterday = datetime.now() - timedelta(days=1)
    iso_date  = yesterday.strftime("%Y-%m-%d")
    filename  = f"alertas/alertas_{iso_date}.xlsx"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx     = await browser.new_context(accept_downloads=True)
        page    = await ctx.new_page()

        # 1. Login
        print("Navegando al login...")
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(2000)
        await page.fill('input[type="text"]', USERNAME)
        await page.fill('input[type="password"]', PASSWORD)
        await page.click('button:has-text("Entrar")')
        await page.wait_for_timeout(5000)
        print(f"URL tras login: {page.url}")

        # 2. Ir a Registro de alertas
        print("Abriendo Registro de alertas...")
        await page.click('a:has-text("Registro de alertas"), li:has-text("Registro de alertas")')
        await page.wait_for_timeout(5000)
        await page.screenshot(path="alerta_01_pagina.png")
        print(f"URL actual: {page.url}")

        # 3. Esperar que cargue la página
        await page.wait_for_selector('button:has-text("Aplicar"), button:has-text("Exportar")', timeout=30000)
        await page.screenshot(path="alerta_02_lista.png")

        # 4. Setear fechas con JavaScript
        print(f"Seteando fecha: {iso_date}")
        await page.evaluate(f"""
            const inputs = document.querySelectorAll('input[type="date"]');
            if (inputs.length >= 2) {{
                inputs[0].value = '{iso_date}';
                inputs[0].dispatchEvent(new Event('input', {{bubbles: true}}));
                inputs[0].dispatchEvent(new Event('change', {{bubbles: true}}));
                inputs[1].value = '{iso_date}';
                inputs[1].dispatchEvent(new Event('input', {{bubbles: true}}));
                inputs[1].dispatchEvent(new Event('change', {{bubbles: true}}));
            }}
        """)
        await page.wait_for_timeout(1000)
        await page.screenshot(path="alerta_03_fechas.png")

        # 5. Aplicar filtro
        print("Aplicando filtro...")
        await page.click('button:has-text("Aplicar")')
        await page.wait_for_timeout(5000)
        await page.screenshot(path="alerta_04_post_aplicar.png")

        # 6. Exportar
        print("Exportando alertas...")
        os.makedirs("alertas", exist_ok=True)
        async with page.expect_download(timeout=30000) as dl_info:
            await page.click('button:has-text("Exportar")')
        download = await dl_info.value
        await download.save_as(filename)
        await browser.close()
        print(f"✅ Descargado: {filename}")
        return filename

async def main():
    filename = await download_alertas()
    print(f"🎉 ¡Listo! Archivo guardado: {filename}")

if __name__ == "__main__":
    asyncio.run(main())
