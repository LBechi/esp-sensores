import asyncio
import os
import requests
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

USERNAME = os.environ["ESP_USERNAME"]
PASSWORD = os.environ["ESP_PASSWORD"]

LOGIN_URL = "https://espdesign.com.ar/#!/login"

async def download_excel() -> str:
    fecha_manual = os.environ.get("FECHA_DESCARGA", "").strip()
    if fecha_manual:
        target_date = datetime.strptime(fecha_manual, "%Y-%m-%d")
    else:
        target_date = datetime.now() - timedelta(days=1)
    iso_date = target_date.strftime("%Y-%m-%d")
    filename = f"datos/sensores_{iso_date}.xlsx"

    export_requests = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx     = await browser.new_context(accept_downloads=True)
        page    = await ctx.new_page()

        # Interceptar todas las requests para capturar la de exportación
        async def capture_request(request):
            url = request.url
            if any(x in url.lower() for x in ["export", "download", "xlsx", "excel", "csv"]):
                print(f"  → Request capturada: {url}")
                export_requests.append({"url": url, "headers": request.headers})

        page.on("request", capture_request)

        # 1. Login
        print("Navegando al login...")
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(2000)
        await page.fill('input[type="text"]', USERNAME)
        await page.fill('input[type="password"]', PASSWORD)
        await page.click('button:has-text("Entrar")')
        await page.wait_for_timeout(5000)
        print(f"URL tras login: {page.url}")

        # 2. Registro de datos
        print("Abriendo Registro de datos...")
        await page.click('a:has-text("Registro de datos"), li:has-text("Registro de datos")')
        await page.wait_for_timeout(5000)
        await page.wait_for_selector('button:has-text("Aplicar")', timeout=30000)

        # 3. Setear fechas
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

        # 4. Aplicar
        print("Aplicando filtro...")
        await page.click('button:has-text("Aplicar")')
        await page.wait_for_timeout(5000)

        # 5. Exportar — capturar cookies antes del click
        cookies = await ctx.cookies()
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

        print("Exportando...")
        os.makedirs("datos", exist_ok=True)

        # Intentar descarga directa primero
        try:
            async with page.expect_download(timeout=10000) as dl_info:
                await page.click('button:has-text("Exportar")')
            download = await dl_info.value
            await download.save_as(filename)
            print(f"✅ Descarga directa exitosa: {filename}")

        except Exception:
            print("Descarga directa no funcionó, esperando request interceptada...")
            await page.wait_for_timeout(5000)
            await page.screenshot(path="sensor_post_exportar.png")

            if export_requests:
                req = export_requests[-1]
                headers = {"Cookie": cookie_str, "User-Agent": "Mozilla/5.0"}

                # El servidor a veces tarda en generar el archivo de exportación,
                # así que reintentamos con espera antes de darlo por fallido.
                max_intentos = 6
                espera_seg = 5
                r = None
                for intento in range(1, max_intentos + 1):
                    print(f"Descargando via requests (intento {intento}/{max_intentos}): {req['url']}")
                    r = requests.get(req["url"], headers=headers, timeout=30)
                    if r.status_code == 200:
                        break
                    print(f"  → Respuesta {r.status_code}, esperando {espera_seg}s antes de reintentar...")
                    await page.wait_for_timeout(espera_seg * 1000)

                r.raise_for_status()
                with open(filename, "wb") as f:
                    f.write(r.content)
                print(f"✅ Descargado via requests: {filename}")
            else:
                # Último recurso: imprimir todas las requests para debug
                print("No se capturó request de exportación.")
                print("Capturando todas las requests del click...")
                all_reqs = []
                page.on("request", lambda r: all_reqs.append(r.url))
                await page.click('button:has-text("Exportar")')
                await page.wait_for_timeout(5000)
                print("Requests generadas:")
                for r in all_reqs:
                    print(f"  {r}")
                raise RuntimeError("No se pudo exportar")

        await browser.close()
        return filename

async def main():
    filename = await download_excel()
    print(f"🎉 ¡Listo! Archivo guardado: {filename}")

if __name__ == "__main__":
    asyncio.run(main())
