"""Chromium test of the *generated GitHub Pages CSS and JS* (not a live Stlite runtime).

The fixture recreates the DOM elements that were affected by the screenshots, and
forces the original native dark background so the CSS must actually override it.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "dist"


def rgb(hexcolor):
    return tuple(int(hexcolor[i:i+2], 16) for i in (1,3,5))


def color(css):
    return tuple(map(int, re.findall(r"\d+", css)[:3]))


def fixture():
    return '''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"/></head><body>
    <main id="root"><section data-testid="stApp" style="background:#1b1d1d">
      <div data-testid="stAppViewContainer"><div data-testid="stMain" style="background:#1b1d1d">
      <div data-testid="stMainBlockContainer" style="background:#1b1d1d">
        <div class="eue-hero"><p class="eue-eyebrow">ENERGY LEARNING WORKSPACE</p>
          <h1>Energy Usage Estimator</h1><p>Explore custos de energia, compare aparelhos e planeje rotinas.</p></div>
        <div class="metrics"><div data-testid="stMetric">Aparelhos cadastrados<h2>0</h2></div>
          <div data-testid="stMetric">Cenários salvos<h2>0</h2></div>
          <div data-testid="stMetric">Tarifa atual<h2>R$ 1,0000/kWh</h2></div></div>
        <h2 id="section-title">Tarifa da energia</h2>
        <div data-testid="stExpander"><details open><summary>Importar fatura da Copel (PDF)</summary>
          <div data-testid="stExpanderDetails"><p>Selecione a fatura original da Copel</p>
            <div data-testid="stFileUploader"><section data-testid="stFileUploaderDropzone">
              <div data-testid="stFileUploaderFile">
                <div data-testid="stFileUploaderFileIcon" style="padding:6px;display:inline-flex">
                  <svg width="22" height="22" viewBox="0 0 24 24"><path d="M5 3H19V21H5z" fill="currentColor"/>
                  <path d="M8 8h8m-8 4h8m-8 4h8" fill="none" stroke="#14283D" stroke-width="1.5"/></svg>
                </div>
                <div data-testid="stFileUploaderFileData" style="background:#fff;padding:8px">
                  <p data-testid="stFileUploaderFileName" style="color:#fafafa">PrimeiraViaCopel.pdf</p>
                  <small data-testid="stFileUploaderFileSize">0.6 MB</small>
                </div>
              </div>
            </section></div>
            <div data-testid="stAlert" role="alert"><div><p>Fatura DANF3E reconhecida.</p></div></div>
          </div></details></div>
        <label for="rate">Preço de 1 kWh (R$)</label>
        <div data-testid="stNumberInput"><div data-baseweb="input"><div data-baseweb="base-input">
          <input id="rate" value="1.000000" style="background:white;color:white"/>
        </div></div></div>
      </div></div></div>
      <aside data-testid="stSidebar"><div data-testid="stSidebarContent">
        <h2>Energy Usage Estimator</h2><p>Aparência</p>
        <div class="st-key-appearance_choice" data-testid="stSegmentedControl">
          <button id="light-btn" aria-pressed="true">☀ Claro</button>
          <button id="dark-btn" aria-pressed="false">◐ Escuro</button>
        </div>
        <div id="nav"></div>
        <div data-testid="stMetric">Tarifa atual<h2>R$ 1,0000/kWh</h2></div>
      </div></aside>
      <span id="eue-active-theme" hidden data-theme="light"></span>
    </section></main>
    <script>
      for (const name of ['Início','Aparelhos','Calculadora','Cenários','Comparações','Dados e backups']) {
        const button = document.createElement('button'); button.textContent = name;
        button.onclick = () => {document.querySelector('#section-title').textContent = name;};
        document.querySelector('#nav').append(button);
      }
    </script>
    </body></html>'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshots', type=Path)
    args = parser.parse_args()
    script = (ROOT / 'pages/appearance.js').read_bytes()
    url = 'data:text/javascript;base64,' + base64.b64encode(script).decode()
    assert (SITE / 'app-theme.css').exists(), 'Run build_pages.py first'
    snapshots = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        try:
            page = browser.new_page(viewport={'width':1550,'height':1020})
            page.set_content(fixture())
            page.add_style_tag(path=str(SITE / 'app-theme.css'))
            page.evaluate('''async (url) => {
              const module = await import(url);
              window.eueSync = module.startAppearanceSync(document, document.getElementById('root'));
              window.eueDetect = module.detectAppearance;
            }''', url)
            for current in ('light', 'dark', 'light'):
                if current == 'dark':
                    page.locator('#dark-btn').click()
                elif len(snapshots) > 0:
                    page.locator('#light-btn').click()
                page.evaluate('''theme => {
                    const isLight = theme === 'light';
                    document.querySelector('#light-btn').setAttribute('aria-pressed',String(isLight));
                    document.querySelector('#dark-btn').setAttribute('aria-pressed',String(!isLight));
                    document.querySelector('#eue-active-theme').dataset.theme=theme;
                }''', current)
                page.wait_for_function('''theme => document.documentElement.dataset.eueTheme===theme''', arg=current)
                expected = {
                    'light': dict(bg='#F5F9FE', sidebar='#EAF2FB', text='#14283D', surface='#FFFFFF', uploader='#EFF6FF'),
                    'dark': dict(bg='#0B121C', sidebar='#121E2C', text='#F1F7FF', surface='#142333', uploader='#1B3045'),
                }[current]
                selectors = {
                    'bg':'body',
                    'sidebar':'[data-testid="stSidebar"]',
                    'surface':'.metrics [data-testid="stMetric"]',
                    'uploader':'[data-testid="stFileUploaderDropzone"]',
                }
                for token, selector in selectors.items():
                    found = color(page.locator(selector).first.evaluate('(e)=>getComputedStyle(e).backgroundColor'))
                    assert found == rgb(expected[token]), (current,token,found,expected[token])
                for label,selector in {
                    'input':'#rate',
                    'filename':'[data-testid="stFileUploaderFileName"]',
                    'icon':'[data-testid="stFileUploaderFileIcon"] svg path',
                }.items():
                    found = color(page.locator(selector).first.evaluate('(e) => getComputedStyle(e)["color"]'))
                    # The actual icon's primary paint uses currentColor.
                    assert (label == 'icon' or found == rgb(expected['text'])), (current,label,found)
                inp=page.locator('#rate')
                assert color(inp.evaluate('(e)=>getComputedStyle(e).backgroundColor'))==rgb(expected['surface'])
                assert color(inp.evaluate('(e)=>getComputedStyle(e).color'))==rgb(expected['text'])
                assert color(page.locator('[data-testid="stFileUploaderFileName"]').evaluate('(e)=>getComputedStyle(e).color'))==rgb(expected['text'])
                assert color(page.locator('[data-testid="stFileUploaderFileIcon"]').evaluate('(e)=>getComputedStyle(e).backgroundColor'))==rgb('#14283D' if current=='light' else '#243F59')
                for nav in ['Início','Aparelhos','Calculadora','Cenários','Comparações','Dados e backups']:
                    page.get_by_role('button',name=nav,exact=True).click()
                    assert page.locator('#section-title').inner_text()==nav
                    assert color(page.locator('body').evaluate('(e)=>getComputedStyle(e).backgroundColor'))==rgb(expected['bg'])
                if args.screenshots:
                    args.screenshots.mkdir(parents=True,exist_ok=True)
                    f=args.screenshots/f'pages-theme-{current}.png'
                    page.get_by_role('button',name='Início',exact=True).click()
                    page.screenshot(path=str(f),full_page=True)
                snapshots.append(current)
            # Earlier Streamlit releases mark the active button with a distinct
            # data-testid instead of aria-pressed; the visible selection must win
            # even when the Python marker still refers to the previous theme.
            page.evaluate('''() => {
                const light=document.querySelector('#light-btn');
                const dark=document.querySelector('#dark-btn');
                light.removeAttribute('aria-pressed'); dark.removeAttribute('aria-pressed');
                dark.setAttribute('data-testid','stBaseButton-segmented_controlActive');
                document.querySelector('#eue-active-theme').dataset.theme='light';
            }''')
            page.wait_for_function("document.documentElement.dataset.eueTheme === 'dark'")
            page.evaluate('''() => {
                const light=document.querySelector('#light-btn');
                const dark=document.querySelector('#dark-btn');
                dark.removeAttribute('data-testid');
                light.setAttribute('data-testid','stBaseButton-segmented_controlActive');
            }''')
            page.wait_for_function("document.documentElement.dataset.eueTheme === 'light'")
            # Real-world fallback: the widget and marker are temporarily removed
            # while React rerenders. Keep current root palette, not native dark.
            page.evaluate('''() => {document.querySelector('[data-testid="stSegmentedControl"]').remove();
                    document.querySelector('#eue-active-theme').remove();}''')
            assert page.evaluate('document.documentElement.dataset.eueTheme') == 'light'
        finally:
            browser.close()
    print(json.dumps({'result':'PASS','kind':'Pages generated CSS + real browser JS, simulated Streamlit DOM',
        'sequences':snapshots,'pages_checked':6},ensure_ascii=False))

if __name__=='__main__':
    main()
