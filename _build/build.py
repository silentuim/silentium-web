#!/usr/bin/env python3
"""Genera las cuatro versiones de idioma del sitio a partir de una sola plantilla.

    python3 _build/build.py            escribe index.html, en/, fr/, de/ y sitemap.xml
    python3 _build/build.py --check    no escribe nada; sale con 1 si algo esta desfasado

Fuente de verdad:
    _build/template.html   estructura, estilos y scripts (una unica copia)
    _build/i18n.json       los textos de los cuatro idiomas

Los cuatro index.html son SALIDA: no se editan a mano. Para cambiar un precio o
un texto se toca la plantilla o el JSON y se vuelve a ejecutar este script, y asi
los cuatro idiomas no pueden desincronizarse.
"""

import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, '_build')

GENERATED_HEADER = """<!DOCTYPE html>
<!--
  ARCHIVO GENERADO - NO EDITAR A MANO.
  Se genera desde _build/template.html + _build/i18n.json con:

      python3 _build/build.py

  Cualquier cambio escrito directamente aqui se perdera en la proxima
  generacion, y ademas dejaria este idioma desincronizado de los otros tres.
-->
"""

FLAGS = {'es': '\U0001F1EA\U0001F1F8', 'en': '\U0001F1EC\U0001F1E7',
         'fr': '\U0001F1EB\U0001F1F7', 'de': '\U0001F1E9\U0001F1EA'}

# Claves de los mensajes de la descarga de AirBot: viajan al JS de cada pagina
# ya traducidas, sin el prefijo con el que se guardan en i18n.json.
AIRBOT_KEYS = ['msgChecking', 'msgOk', 'msgNoSub', 'msgInvalid', 'msgError']


def attr_escape(value):
    """Escapa un texto que se va a incrustar dentro de un atributo HTML."""
    return (value.replace('&', '&amp;')
                 .replace('<', '&lt;')
                 .replace('>', '&gt;')
                 .replace('"', '&quot;'))


def in_attribute(html, pos):
    """True si la posicion cae dentro de una etiqueta, o sea en un atributo."""
    return html.rfind('<', 0, pos) > html.rfind('>', 0, pos)


def ld_json_span(html):
    start = html.index('<script type="application/ld+json">')
    return start, html.index('</script>', start)


def hreflang_block(cfg):
    origin = cfg['site']['origin']
    lines = []
    for code in cfg['site']['order']:
        url = origin + cfg['langs'][code]['path']
        lines.append('<link rel="alternate" hreflang="%s" href="%s">' % (code, url))
    default = cfg['langs'][cfg['site']['default']]['path']
    lines.append('<link rel="alternate" hreflang="x-default" href="%s">' % (origin + default))
    return '\n'.join(lines)


def og_locale_alt(cfg, current):
    return '\n'.join(
        '<meta property="og:locale:alternate" content="%s">' % cfg['langs'][c]['ogLocale']
        for c in cfg['site']['order'] if c != current)


def lang_switch_block(cfg, current):
    label = attr_escape(cfg['langs'][current]['ui.langLabel'])
    out = ['<div class="lang-switch" role="group" aria-label="%s">' % label]
    for code in cfg['site']['order']:
        data = cfg['langs'][code]
        attrs = 'href="%s" hreflang="%s" lang="%s"' % (data['path'], code, code)
        if code == current:
            attrs += ' aria-current="page"'
        else:
            attrs += ' title="%s"' % attr_escape(data['langName'])
        out.append('        <a %s>%s %s</a>' % (attrs, FLAGS[code], code.upper()))
    out.append('      </div>')
    return '\n'.join(out)


def lang_hints(cfg):
    """Los avisos van en los cuatro idiomas porque el aviso se muestra en el
    idioma que se sugiere, no en el de la pagina que lo ensena."""
    return {c: {'text': cfg['langs'][c]['banner.text'],
                'cta': cfg['langs'][c]['banner.cta'],
                'close': cfg['langs'][c]['banner.close'],
                'path': cfg['langs'][c]['path']}
            for c in cfg['site']['order']}


def render(template, cfg, code):
    data = cfg['langs'][code]
    origin = cfg['site']['origin']
    url = origin + data['path']

    blocks = {
        'generatedHeader': GENERATED_HEADER,
        'hreflang': hreflang_block(cfg),
        'ogLocaleAlt': og_locale_alt(cfg, code),
        'langSwitch': lang_switch_block(cfg, code),
        'url': url,
        'lang': code,
        'ogLocale': data['ogLocale'],
        'airbotMessages': json.dumps(
            {k: data['apps.airbot.' + k] for k in AIRBOT_KEYS},
            ensure_ascii=False, indent=2),
        'langHints': json.dumps(lang_hints(cfg), ensure_ascii=False, indent=2),
    }

    ld_start, ld_end = ld_json_span(template)
    out, cursor = [], 0
    for m in re.finditer(r'\{\{([a-zA-Z][a-zA-Z0-9._]*)\}\}', template):
        key = m.group(1)
        if key in blocks:
            value = blocks[key]
        elif key in data:
            value = data[key]
        else:
            raise KeyError('%s: clave sin traduccion: %s' % (code, key))

        if key not in ('generatedHeader', 'hreflang', 'ogLocaleAlt', 'langSwitch',
                       'airbotMessages', 'langHints'):
            if ld_start <= m.start() < ld_end:
                # Dentro del JSON-LD manda el escapado de JSON, no el de HTML.
                value = json.dumps(value, ensure_ascii=False)[1:-1]
            elif in_attribute(template, m.start()):
                value = attr_escape(value)

        out.append(template[cursor:m.start()])
        out.append(value)
        cursor = m.end()
    out.append(template[cursor:])
    return ''.join(out)


def sitemap(cfg, lastmod):
    origin = cfg['site']['origin']
    order = cfg['site']['order']
    default = cfg['langs'][cfg['site']['default']]['path']

    alts = ''.join(
        '\n    <xhtml:link rel="alternate" hreflang="%s" href="%s"/>' % (c, origin + cfg['langs'][c]['path'])
        for c in order)
    alts += '\n    <xhtml:link rel="alternate" hreflang="x-default" href="%s"/>' % (origin + default)

    entries = []
    for code in order:
        entries.append(
            '  <url>\n'
            '    <loc>%s</loc>%s\n'
            '    <lastmod>%s</lastmod>\n'
            '    <changefreq>monthly</changefreq>\n'
            '    <priority>%s</priority>\n'
            '  </url>' % (origin + cfg['langs'][code]['path'], alts, lastmod,
                          '1.0' if code == cfg['site']['default'] else '0.9'))

    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!--\n'
            '  Una entrada por idioma. Cada una repite el juego completo de hreflang,\n'
            '  igual que el <head> de las paginas: es la misma senal por dos vias.\n'
            '  Generado por _build/build.py; no editar a mano.\n'
            '-->\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
            '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + '\n'.join(entries) + '\n</urlset>\n')


def outputs(cfg, template, lastmod):
    files = {}
    for code in cfg['site']['order']:
        path = cfg['langs'][code]['path'].strip('/')
        rel = os.path.join(path, 'index.html') if path else 'index.html'
        files[rel] = render(template, cfg, code)
    files['sitemap.xml'] = sitemap(cfg, lastmod)
    return files


def main():
    check = '--check' in sys.argv
    cfg = json.load(open(os.path.join(BUILD, 'i18n.json'), encoding='utf-8'))
    template = open(os.path.join(BUILD, 'template.html'), encoding='utf-8').read()

    existing_map = os.path.join(ROOT, 'sitemap.xml')
    if check and os.path.exists(existing_map):
        found = re.search(r'<lastmod>([\d-]+)</lastmod>', open(existing_map, encoding='utf-8').read())
        lastmod = found.group(1) if found else date.today().isoformat()
    else:
        lastmod = date.today().isoformat()

    files = outputs(cfg, template, lastmod)

    stale = []
    for rel, content in sorted(files.items()):
        full = os.path.join(ROOT, rel)
        current = open(full, encoding='utf-8').read() if os.path.exists(full) else None
        if current == content:
            print('  = %s' % rel)
            continue
        stale.append(rel)
        if check:
            print('  ! %s DESFASADO' % rel)
        else:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            open(full, 'w', encoding='utf-8').write(content)
            print('  + %s (%d bytes)' % (rel, len(content.encode())))

    if check and stale:
        print('\nHay %d archivo(s) que no coinciden con la plantilla.' % len(stale))
        print('Alguien los edito a mano, o falta ejecutar: python3 _build/build.py')
        return 1
    print('\nOK: %d archivos generados desde _build/' % len(files) if not check
          else '\nOK: todo lo publicado coincide con la plantilla.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
