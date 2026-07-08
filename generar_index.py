#!/usr/bin/env python3
"""
generar_index.py

Genera docs/index.html: una landing page que enlaza los dashboards
semanal/mensual y lista los gráficos diarios disponibles en docs/diario/,
más recientes primero.

Uso:
    python3 generar_index.py --docs-dir docs
"""

import argparse
from pathlib import Path

PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Monitoreo de Sensores</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 780px; margin: 40px auto; padding: 0 20px;
    color: #1f2937; background: #f9fafb;
  }}
  h1 {{ font-size: 1.5rem; margin-bottom: 4px; }}
  p.subtitulo {{ color: #6b7280; margin-top: 0; }}
  .tarjetas {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 24px; }}
  .tarjeta {{
    background: white; border: 1px solid #e5e7eb; border-radius: 10px;
    padding: 20px; text-decoration: none; color: inherit;
    transition: box-shadow 0.15s ease;
  }}
  .tarjeta:hover {{ box-shadow: 0 2px 10px rgba(0,0,0,0.08); }}
  .tarjeta h2 {{ font-size: 1.05rem; margin: 0 0 6px 0; color: #2563eb; }}
  .tarjeta p {{ margin: 0; font-size: 0.9rem; color: #6b7280; }}
  .seccion {{ margin-top: 36px; }}
  .seccion h2 {{ font-size: 1.1rem; border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; }}
  ul.dias {{ list-style: none; padding: 0; }}
  ul.dias li a {{
    display: block; padding: 8px 12px; text-decoration: none;
    color: #2563eb; border-radius: 6px;
  }}
  ul.dias li a:hover {{ background: #eef2ff; }}
  footer {{ margin-top: 40px; font-size: 0.8rem; color: #9ca3af; }}
</style>
</head>
<body>
  <h1>🌡️ Monitoreo de Sensores</h1>
  <p class="subtitulo">Temperaturas y alertas de heladeras, freezers y ambiente</p>

  <div class="tarjetas">
    <a class="tarjeta" href="reporte_semanal.html">
      <h2>Vista semanal</h2>
      <p>Últimos 7 días, todos los sensores, interactivo</p>
    </a>
    <a class="tarjeta" href="reporte_mensual.html">
      <h2>Vista mensual</h2>
      <p>Últimos 30 días, todos los sensores, interactivo</p>
    </a>
  </div>

  <div class="seccion">
    <h2>Gráficos diarios</h2>
    <ul class="dias">
{items}
    </ul>
  </div>

  <footer>Última actualización: {actualizado}</footer>
</body>
</html>
"""

ITEM_PLANTILLA = '      <li><a href="diario/{fecha}/dashboard_general.png">{fecha}</a></li>'


def main():
    parser = argparse.ArgumentParser(description="Genera docs/index.html")
    parser.add_argument("--docs-dir", default="docs", help="Carpeta docs/ del repo")
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    diario_dir = docs_dir / "diario"

    fechas = []
    if diario_dir.exists():
        fechas = sorted([p.name for p in diario_dir.iterdir() if p.is_dir()], reverse=True)

    if fechas:
        items = "\n".join(ITEM_PLANTILLA.format(fecha=f) for f in fechas[:30])
    else:
        items = '      <li style="color:#9ca3af; padding: 8px 12px;">Todavía no hay gráficos diarios generados</li>'

    from datetime import datetime
    html = PLANTILLA.format(items=items, actualizado=datetime.now().strftime("%Y-%m-%d %H:%M"))

    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"index.html generado con {len(fechas)} días listados")


if __name__ == "__main__":
    main()
