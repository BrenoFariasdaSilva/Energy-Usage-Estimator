"""Browser-only CSS contrast smoke test against a Streamlit-shaped fixture.

This is NOT an end-to-end Streamlit test: it intentionally does not start
Streamlit or upload files to a running server. For reproducibility it uses
Chromium and the application's real CSS against representative DOM nodes.

Install optional dependency: pip install playwright
Then install its browser or use a preinstalled Chromium:
  python -m playwright install chromium
  python scripts/verify_theme_fixture.py --screenshots /tmp/eue-screenshots
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from energy_estimator.ui_theme import THEMES, theme_css  # noqa: E402

PAGES = ("Início", "Aparelhos", "Calculadora", "Cenários", "Comparações", "Dados e backups")


def rgb(hex_color: str) -> tuple[int, int, int]:
    return tuple(int(hex_color[index : index + 2], 16) for index in (1, 3, 5))


def contrast(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        s = value / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    def luminance(c: tuple[int, int, int]) -> float:
        return sum(w * channel(v) for w, v in zip((0.2126, 0.7152, 0.0722), c))

    a, b = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def html_fixture(theme: str) -> str:
    # Intentionally emulate nested Streamlit structure and inherited *opposing*
    # native colors to detect regressions that previously produced dark-on-dark.
    return (
        """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
      <style>
        body {margin:0;font-family:Arial,sans-serif;color:#f0f0f0;background:#202020}
        [data-testid="stApp"],[data-testid="stMain"],[data-testid="stSidebar"] {background:#202020}
        [data-testid="stFileUploaderFile"] {display:flex;align-items:center;gap:8px;border-radius:8px;padding:8px;}
        [data-testid="stFileUploaderFileIcon"] {
          height:32px;width:32px;display:flex;align-items:center;justify-content:center;
        }
        #app-layout {display:flex;min-height:100vh}
        [data-testid="stSidebar"] {width:270px;box-sizing:border-box;padding:22px;flex-shrink:0}
        [data-testid="stAppViewContainer"] {flex:1}
        [data-testid="stMain"] {max-width:1080px;padding:24px 40px;margin:auto;box-sizing:border-box}
        [data-testid="stMetric"] {padding:15px;flex:1}
        .metrics {display:flex;gap:12px;margin:12px 0}
        [data-testid="stExpander"] {padding:15px}
        [data-testid="stExpander"] summary {padding:10px}
        [data-testid="stFileUploaderDropzone"] {padding:12px;}
        [data-testid="stAlert"] {margin-top:12px;padding:12px}
        [data-testid="stFileUploaderFileName"] {font-size:15px}
        [data-testid="stFileUploaderFileSize"] {font-size:13px}
        /* Deliberately emulate the BASE Streamlit light-theme conflicts
           reproduced in the supplied screenshots: a white chip with white
           file text, and a white input with white input text. */
        [data-testid="stFileUploaderFileData"] {background-color:#f2f7ff;color:#f2f7ff}
        [data-testid="stFileUploaderFileData"] p {color:#f2f7ff}
        [data-testid="stNumberInput"] input {
          background-color:#fff;color:#fff;-webkit-text-fill-color:#fff;
        }
      </style></head><body>
      <div data-testid="stApp"><div id="app-layout">
      <aside data-testid="stSidebar"><h2>Energy Usage Estimator</h2><p>Painel de estimativas de eletricidade</p>
      <p>Aparência</p><div data-testid="stSegmentedControl">
      <button id="light-btn">Claro</button><button id="dark-btn">Escuro</button></div>
      <hr><p>Menu</p><nav id="nav"></nav><hr>
      <div data-testid="stMetric"><small>Tarifa atual</small><div data-testid="stMetricValue">R$ 1,0265/kWh</div></div>
      </aside><div data-testid="stAppViewContainer"><div data-testid="stMain"><div data-testid="stMainBlockContainer">
      <div class="eue-hero"><p class="eue-eyebrow">ENERGY LEARNING WORKSPACE</p>
      <h1>Energy Usage Estimator</h1><p>Explore custos de energia e planeje rotinas de consumo.</p></div>
      <div class="metrics"><div data-testid="stMetric">Aparelhos cadastrados<h2>0</h2></div>
      <div data-testid="stMetric">Cenários salvos<h2>0</h2></div>
      <div data-testid="stMetric">Tarifa atual<h2>R$ 1,0265/kWh</h2></div></div>
      <h2 id="section-title">Tarifa da energia</h2>
      <div data-testid="stExpander"><details open><summary>Importar fatura da Copel (PDF)</summary>
      <div data-testid="stExpanderDetails"><p>Selecione a fatura original da Copel</p>
      <div data-testid="stFileUploader"><section data-testid="stFileUploaderDropzone">
      <div data-testid="stFileUploaderFile">
      <div data-testid="stFileUploaderFileIcon"><svg viewBox="0 0 24 24" width="19" height="19">
      <rect x="5" y="3" width="14" height="18" rx="1" fill="none" stroke="currentColor" stroke-width="2"/>
      <path d="M8 8h8m-8 4h8m-8 4h6" fill="none" stroke="currentColor" stroke-width="1.6"/></svg></div>
      <div data-testid="stFileUploaderFileData"><div><p data-testid="stFileUploaderFileName">PrimeiraViaCopel.pdf</p>
      <small data-testid="stFileUploaderFileSize">0.6MB</small></div></div>
      <button aria-label="Remover">×</button></div>
      <!-- Other Streamlit releases put the test ID directly on a filled SVG. -->
      <div data-testid="stFileUploaderFile" id="alternate-file" style="margin-top:10px">
      <svg data-testid="stFileUploaderFileIcon" id="direct-svg" viewBox="0 0 24 24" width="32" height="32">
      <path d="M7 3h7l4 4v14H7z" fill="currentColor"/>
      <path d="M10 11h5v2h-5z" fill="#14283D"/></svg>
      <div data-testid="stFileUploaderFileData"><p data-testid="stFileUploaderFileName">OutraFatura.pdf</p></div></div>
      </section></div>
      <div data-testid="stAlert" role="alert"><div>
      <p>Fatura DANF3E da Copel reconhecida. Confira os valores antes de aplicar.</p></div></div>
      <div class="metrics"><div data-testid="stMetric">Referência<h2>11/2026</h2></div>
      <div data-testid="stMetric">Consumo faturado<h2>168 kWh</h2></div>
      <div data-testid="stMetric">Total a pagar<h2>R$ 192,72</h2></div></div>
      <div data-testid="stMetric">Tarifa calculada<h2>R$ 1,026488/kWh</h2></div>
      </div></details></div>
      <p>Como deseja informar o custo da energia?</p><div data-testid="stNumberInput">
      <div data-baseweb="input"><div data-baseweb="base-input">
      <input type="number" value="1.026488"/></div></div></div>
      <p><button data-testid="stBaseButton-primary">Salvar tarifa</button></p>
      </div></div></div></div></div>
      """
        + theme_css(theme)
        + """
      <script>
      let pages = """
        + json.dumps(PAGES, ensure_ascii=False)
        + """;
      const nav=document.querySelector('#nav');
      pages.forEach((name,index)=>{
        const el=document.createElement('button');
        el.textContent=name;
        el.style.display='block';
        el.style.marginBottom='8px';
        el.onclick=()=>{document.querySelector('#section-title').textContent=name;
                     document.querySelector('#section-title').dataset.page=String(index)};
        nav.append(el)
      });
      for(const name of ['light','dark']){
        document.querySelector('#'+name+'-btn').onclick=()=>{
          document.querySelector('#eue-active-theme').dataset.theme=name
        }
      }
      </script></body></html>"""
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshots", type=Path, help="Optional screenshot output directory")
    parser.add_argument("--chromium", type=str, help="Path to an existing Chromium executable")
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright

    results: list[dict] = []
    with sync_playwright() as playwright:
        args_launch = {"headless": True, "args": ["--no-sandbox"]}
        if args.chromium:
            args_launch["executable_path"] = args.chromium
        browser = playwright.chromium.launch(**args_launch)
        try:
            page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
            page.set_content(html_fixture("light"))
            for theme in ("light", "dark", "light"):
                page.locator("#" + theme + "-btn").click()
                palette = THEMES[theme]
                expected = {
                    "body": palette.background,
                    "sidebar": palette.sidebar,
                    "metric": palette.surface,
                    "uploader": palette.surface_alt,
                    "alert": palette.surface_alt,
                    "file-icon": "#14283D" if theme == "light" else "#243F59",
                }
                selectors = {
                    "body": "body",
                    "sidebar": '[data-testid="stSidebar"]',
                    "metric": '.metrics [data-testid="stMetric"]',
                    "uploader": '[data-testid="stFileUploaderDropzone"]',
                    "alert": '[data-testid="stAlert"]',
                    "file-icon": '[data-testid="stFileUploaderFileIcon"]',
                }
                for element, selector in selectors.items():
                    background = page.locator(selector).first.evaluate("(e)=>getComputedStyle(e).backgroundColor")
                    assert background == "rgb(" + ", ".join(map(str, rgb(expected[element]))) + ")", (
                        theme,
                        element,
                        background,
                        expected[element],
                    )
                # Assert the precise regression cases from the user screenshots:
                # white text in a white input, pale filename on a white pill,
                # and a filled document glyph disappearing in the light theme.
                input_selector = '[data-testid="stNumberInput"] input'
                input_color = page.locator(input_selector).evaluate("(e)=>getComputedStyle(e).color")
                input_bg = page.locator(input_selector).evaluate("(e)=>getComputedStyle(e).backgroundColor")
                num_fg = tuple(map(int, re.findall(r"\d+", input_color)[:3]))
                num_bg = tuple(map(int, re.findall(r"\d+", input_bg)[:3]))
                assert num_bg == rgb(palette.surface), (theme, "numeric input background", input_bg)
                assert num_fg == rgb(palette.text), (theme, "numeric input text", input_color)
                assert contrast(num_fg, num_bg) >= 4.5, (theme, "numeric input contrast")
                # Simulate editing the input and switching palettes without any rerun.
                page.locator(input_selector).fill("1.026488")
                assert page.locator(input_selector).input_value() == "1.026488"
                file_info_bg = page.locator('[data-testid="stFileUploaderFileData"]').first.evaluate(
                    "(e)=>getComputedStyle(e).backgroundColor"
                )
                assert file_info_bg == "rgba(0, 0, 0, 0)", (theme, "file pill", file_info_bg)
                for icon in page.locator('[data-testid="stFileUploaderFileIcon"]').all():
                    icon_bg = icon.evaluate("(e)=>getComputedStyle(e).backgroundColor")
                    assert icon_bg == "rgb(" + ", ".join(map(str, rgb(expected["file-icon"]))) + ")"
                    icon_fg = icon.evaluate("(e)=>getComputedStyle(e).color")
                    assert (
                        icon_fg
                        == "rgb(" + ", ".join(map(str, rgb("#FFFFFF" if theme == "light" else "#F1F7FF"))) + ")"
                    ), (theme, "icon fg", icon_fg)
                direct_glyph = page.locator("#direct-svg path").first.evaluate("(e)=>getComputedStyle(e).fill")
                assert (
                    direct_glyph
                    == "rgb(" + ", ".join(map(str, rgb("#FFFFFF" if theme == "light" else "#F1F7FF"))) + ")"
                ), (theme, "filled glyph", direct_glyph)
                # Ensure the line-art variant remains visible, too.
                stroke = page.locator('[data-testid="stFileUploaderFileIcon"] rect').first.evaluate(
                    "(e)=>getComputedStyle(e).stroke"
                )
                assert (
                    stroke == "rgb(" + ", ".join(map(str, rgb("#FFFFFF" if theme == "light" else "#F1F7FF"))) + ")"
                ), (theme, "outline glyph", stroke)
                results.append(
                    {"theme": theme, "element": "number_input", "contrast": round(contrast(num_fg, num_bg), 2)}
                )
                # Detect inaccessible filenames and alerts; apply the 4.5:1 WCAG normal text criterion.
                for element, selector in {
                    "filename": '[data-testid="stFileUploaderFileName"]',
                    "size": '[data-testid="stFileUploaderFileSize"]',
                    "alert": '[data-testid="stAlert"] p',
                }.items():
                    fg, bg = page.locator(selector).first.evaluate("""(e)=>{
                       let fg=getComputedStyle(e).color;
                       let parent=e;
                       let bg='rgba(0, 0, 0, 0)';
                       while(parent && (bg==='rgba(0, 0, 0, 0)' || bg==='transparent')){
                         bg=getComputedStyle(parent).backgroundColor;
                         parent=parent.parentElement;
                       }
                       return [fg,bg]}
                    """)
                    fg_rgb = tuple(map(int, re.findall(r"\d+", fg)[:3]))
                    bg_rgb = tuple(map(int, re.findall(r"\d+", bg)[:3]))
                    ratio = contrast(fg_rgb, bg_rgb)
                    assert ratio >= 4.5, (theme, element, ratio, fg, bg)
                    results.append({"theme": theme, "element": element, "contrast": round(ratio, 2)})
                for index, name in enumerate(PAGES):
                    page.locator("#nav button").nth(index).click()
                    assert page.locator("#section-title").inner_text() == name
                    assert page.locator("body").evaluate("(e)=>getComputedStyle(e).backgroundColor") == (
                        "rgb(" + ", ".join(map(str, rgb(palette.background))) + ")"
                    )
                if args.screenshots and theme not in [r["theme"] for r in results if "screenshot" in r]:
                    args.screenshots.mkdir(parents=True, exist_ok=True)
                    name = f"theme-{theme}.png"
                    page.locator("#nav button").first.click()
                    page.screenshot(path=str(args.screenshots / name), full_page=True)
                    results.append({"theme": theme, "screenshot": name})
        finally:
            browser.close()
    print(
        json.dumps(
            {"status": "PASS", "kind": "browser_css_fixture_not_streamlit_e2e", "results": results},
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
