#!/usr/bin/env python3
"""Genera el sitio entero a partir de una sola plantilla y un solo JSON por idioma.

    python3 _build/build.py            escribe index.html, en/, fr/, de/, blog/ y sitemap.xml
    python3 _build/build.py --check    no escribe nada; sale con 1 si algo esta desfasado

Fuente de verdad:
    _build/template.html   estructura, estilos y scripts de la home (una unica copia)
    _build/blog-index.html plantilla del indice del blog
    _build/blog-post.html  plantilla del articulo
    _build/i18n.json       los textos de los cuatro idiomas
    _build/blog.json       slug, fecha y cuerpo de cada articulo

Las dos plantillas del blog no repiten ni el CSS ni la cabecera ni el pie: los
piden con {{styles}}, {{siteTop}} y {{siteFooter}}, y build.py los recorta de
template.html antes de renderizar. Asi el sitio sigue teniendo una sola hoja de
estilos y una sola cabecera, y el blog no puede quedarse con el diseno viejo.

Todos los HTML publicados son SALIDA: no se editan a mano. Para cambiar un
precio, un texto o un articulo se toca la plantilla o el JSON y se vuelve a
ejecutar este script, y asi los cuatro idiomas no pueden desincronizarse.
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

# Bloques que build.py compone ya como HTML o como JSON: no se escapan al
# insertarlos, a diferencia de los textos que vienen de i18n.json.
RAW_BLOCKS = frozenset([
    'generatedHeader', 'hreflang', 'ogLocaleAlt', 'langSwitch', 'airbotMessages',
    'langHints', 'styles', 'siteTop', 'siteFooter', 'postBody', 'blogCards',
    'blogPostList',
])

# Nombres de producto que el traductor del navegador no debe renombrar. En el
# cuerpo de los articulos se envuelven solos; en i18n.json el <span> se escribe
# a mano. El de mas de una palabra va primero: la alternativa del regex se
# resuelve en orden y 'Silentium' se comeria 'Silentium Supernova'.
BRANDS = ['Silentium Supernova', 'AirBot Radar', 'Hydra Pocket', 'MindTrace',
          'BinauralNature', 'ZeroTrace Guardian', 'Silentium']
# El espacio de alrededor entra DENTRO del span a proposito: el traductor
# reescribe los nodos de texto vecinos y se lleva por delante el que quede
# fuera ('AirBot Radargratis'). Ver el comentario de i18n.json.
BRAND_RE = re.compile(r'[ ]?(?:%s)[ ]?' % '|'.join(re.escape(b) for b in BRANDS))

MONTHS = {
    'es': ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
           'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'],
    'en': ['January', 'February', 'March', 'April', 'May', 'June', 'July',
           'August', 'September', 'October', 'November', 'December'],
    'fr': ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
           'août', 'septembre', 'octobre', 'novembre', 'décembre'],
    'de': ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli',
           'August', 'September', 'Oktober', 'November', 'Dezember'],
}


def text_escape(value):
    """Escapa un texto que se va a incrustar como contenido de un elemento."""
    return value.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def attr_escape(value):
    """Escapa un texto que se va a incrustar dentro de un atributo HTML."""
    return text_escape(value).replace('"', '&quot;')


def in_attribute(html, pos):
    """True si la posicion cae dentro de una etiqueta, o sea en un atributo."""
    return html.rfind('<', 0, pos) > html.rfind('>', 0, pos)


def ld_json_span(html):
    start = html.find('<script type="application/ld+json">')
    if start < 0:
        return -1, -1
    return start, html.index('</script>', start)


def format_date(iso, code):
    y, m, d = (int(part) for part in iso.split('-'))
    month = MONTHS[code][m - 1]
    if code == 'es':
        return '%d de %s de %d' % (d, month, y)
    if code == 'de':
        return '%d. %s %d' % (d, month, y)
    if code == 'fr':
        return '%s %s %d' % ('1er' if d == 1 else d, month, y)
    return '%d %s %d' % (d, month, y)


# ---------------------------------------------------------------- rutas

def home_paths(cfg):
    return {c: cfg['langs'][c]['path'] for c in cfg['site']['order']}


def blog_paths(cfg):
    return {c: cfg['langs'][c]['path'] + 'blog/' for c in cfg['site']['order']}


def post_paths(cfg, post):
    return {c: cfg['langs'][c]['path'] + 'blog/' + post['slug'] + '/'
            for c in cfg['site']['order']}


# ------------------------------------------------------- bloques comunes

def hreflang_block(cfg, paths):
    origin = cfg['site']['origin']
    lines = []
    for code in cfg['site']['order']:
        lines.append('<link rel="alternate" hreflang="%s" href="%s">' % (code, origin + paths[code]))
    lines.append('<link rel="alternate" hreflang="x-default" href="%s">'
                 % (origin + paths[cfg['site']['default']]))
    return '\n'.join(lines)


def og_locale_alt(cfg, current):
    return '\n'.join(
        '<meta property="og:locale:alternate" content="%s">' % cfg['langs'][c]['ogLocale']
        for c in cfg['site']['order'] if c != current)


def lang_switch_block(cfg, current, paths):
    """El selector no manda siempre a la home: manda a ESTA misma pagina en el
    otro idioma. En un articulo, cambiar de idioma no debe perder el articulo."""
    label = attr_escape(cfg['langs'][current]['ui.langLabel'])
    out = ['<div class="lang-switch" role="group" aria-label="%s">' % label]
    for code in cfg['site']['order']:
        data = cfg['langs'][code]
        attrs = 'href="%s" hreflang="%s" lang="%s"' % (paths[code], code, code)
        if code == current:
            attrs += ' aria-current="page"'
        else:
            attrs += ' title="%s"' % attr_escape(data['langName'])
        out.append('        <a %s>%s %s</a>' % (attrs, FLAGS[code], code.upper()))
    out.append('      </div>')
    return '\n'.join(out)


def lang_hints(cfg, paths):
    """Los avisos van en los cuatro idiomas porque el aviso se muestra en el
    idioma que se sugiere, no en el de la pagina que lo ensena."""
    return {c: {'text': cfg['langs'][c]['banner.text'],
                'cta': cfg['langs'][c]['banner.cta'],
                'close': cfg['langs'][c]['banner.close'],
                'path': paths[c]}
            for c in cfg['site']['order']}


def common_blocks(cfg, code, paths):
    """Lo que necesita cualquier pagina del sitio, sea la home o un articulo."""
    return {
        'generatedHeader': GENERATED_HEADER,
        'hreflang': hreflang_block(cfg, paths),
        'ogLocaleAlt': og_locale_alt(cfg, code),
        'langSwitch': lang_switch_block(cfg, code, paths),
        'url': cfg['site']['origin'] + paths[code],
        'lang': code,
        'ogLocale': cfg['langs'][code]['ogLocale'],
        'home': cfg['langs'][code]['path'],
        'blogIndex': cfg['langs'][code]['path'] + 'blog/',
    }


def render(template, cfg, code, blocks):
    data = cfg['langs'][code]
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

        if key not in RAW_BLOCKS:
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


# ------------------------------------------------------------- el blog

def layout_parts(template):
    """Recorta de la plantilla de la home las piezas que comparte todo el sitio.

    Se recortan en vez de duplicarse para que anadir un enlace a la cabecera o
    tocar un color siga siendo un cambio en un unico sitio. Se sustituyen en la
    plantilla ANTES de renderizar, no como valor de un bloque, para que los
    {{...}} que traen dentro (el selector de idioma, el nav) se resuelvan."""
    def cut(open_tag, close_tag):
        start = template.index(open_tag)
        return template[start:template.index(close_tag, start) + len(close_tag)]

    return {
        'styles': cut('<style>', '</style>'),
        'siteTop': cut('<div class="light-rays">', '</header>'),
        'siteFooter': cut('<footer>', '</footer>'),
    }


def protect_brands(escaped_text):
    return BRAND_RE.sub(lambda m: '<span translate="no">%s</span>' % m.group(0), escaped_text)


def inline(text):
    return protect_brands(text_escape(text))


def body_html(blocks, post_id, code):
    """Convierte el cuerpo en texto plano de blog.json en HTML.

    Tres formas y ninguna mas: '## ' es un <h2>, un bloque de lineas que
    empiezan por '- ' es un <ul>, y todo lo demas es un <p>. El texto se escapa
    siempre, asi que un articulo no puede colar marcado en la pagina."""
    out = []
    for block in blocks:
        if block.startswith('## '):
            out.append('      <h2>%s</h2>' % inline(block[3:].strip()))
        elif block.startswith('- '):
            items = []
            for line in block.split('\n'):
                if not line.startswith('- '):
                    raise ValueError('%s/%s: linea de lista sin "- ": %r'
                                     % (post_id, code, line[:40]))
                items.append('        <li>%s</li>' % inline(line[2:].strip()))
            out.append('      <ul>\n%s\n      </ul>' % '\n'.join(items))
        else:
            out.append('      <p>%s</p>' % inline(block))
    return '\n'.join(out)


def post_card(cfg, code, post, indent='      '):
    """La misma tarjeta que la home, para que el indice no invente otro estilo."""
    data = cfg['langs'][code]
    path = post_paths(cfg, post)[code]
    return (
        '%s<a class="blog-card" href="%s">\n'
        '%s  <span class="tag">%s</span>\n'
        '%s  <h3>%s</h3>\n'
        '%s  <p>%s</p>\n'
        '%s  <time datetime="%s">%s</time>\n'
        '%s</a>' % (
            indent, path,
            indent, data['blog.%s.tag' % post['id']],
            indent, data['blog.%s.title' % post['id']],
            indent, data['blog.%s.desc' % post['id']],
            indent, post['date'], format_date(post['date'], code),
            indent))


def blog_post_list_ld(cfg, code, posts):
    origin = cfg['site']['origin']
    data = cfg['langs'][code]
    items = [{
        '@type': 'BlogPosting',
        '@id': origin + post_paths(cfg, p)[code] + '#articulo',
        'url': origin + post_paths(cfg, p)[code],
        'headline': data['blog.%s.title' % p['id']],
        'datePublished': p['date'],
    } for p in posts]
    return json.dumps(items, ensure_ascii=False, indent=6)[:-1] + '      ]'


def blog_files(cfg, blog, layout, code):
    """El indice y los tres articulos de un idioma."""
    posts = blog['posts']
    data = cfg['langs'][code]
    files = {}

    index_tpl = fill_layout(open(os.path.join(BUILD, 'blog-index.html'), encoding='utf-8').read(), layout)
    blocks = common_blocks(cfg, code, blog_paths(cfg))
    blocks['blogCards'] = '\n\n'.join(post_card(cfg, code, p) for p in posts)
    blocks['blogPostList'] = blog_post_list_ld(cfg, code, posts)
    files[rel_path(blog_paths(cfg)[code])] = render(index_tpl, cfg, code, blocks)

    post_tpl = fill_layout(open(os.path.join(BUILD, 'blog-post.html'), encoding='utf-8').read(), layout)
    for post in posts:
        blocks = common_blocks(cfg, code, post_paths(cfg, post))
        title = data['blog.%s.title' % post['id']]
        blocks.update({
            'postTitle': title,
            'postMetaTitle': '%s — Silentium Supernova' % title,
            'postTag': data['blog.%s.tag' % post['id']],
            'postDesc': data['blog.%s.desc' % post['id']],
            'postDate': format_date(post['date'], code),
            'postDateIso': post['date'],
            'postBody': body_html(post['body'][code], post['id'], code),
            'blogUrl': cfg['site']['origin'] + blog_paths(cfg)[code],
        })
        files[rel_path(post_paths(cfg, post)[code])] = render(post_tpl, cfg, code, blocks)

    return files


def fill_layout(template, layout):
    for key, value in layout.items():
        template = template.replace('{{%s}}' % key, value)
    return template


def rel_path(url_path):
    return os.path.join(url_path.strip('/'), 'index.html') if url_path.strip('/') else 'index.html'


# ----------------------------------------------------------- sitemap

def sitemap(cfg, blog, lastmod):
    origin = cfg['site']['origin']
    order = cfg['site']['order']
    default = cfg['site']['default']

    def group(paths, mod, changefreq, priority, top_priority=None):
        alts = ''.join(
            '\n    <xhtml:link rel="alternate" hreflang="%s" href="%s"/>' % (c, origin + paths[c])
            for c in order)
        alts += '\n    <xhtml:link rel="alternate" hreflang="x-default" href="%s"/>' % (origin + paths[default])
        return ['  <url>\n'
                '    <loc>%s</loc>%s\n'
                '    <lastmod>%s</lastmod>\n'
                '    <changefreq>%s</changefreq>\n'
                '    <priority>%s</priority>\n'
                '  </url>' % (origin + paths[c], alts, mod, changefreq,
                              top_priority if (top_priority and c == default) else priority)
                for c in order]

    entries = group(home_paths(cfg), lastmod, 'monthly', '0.9', top_priority='1.0')
    entries += group(blog_paths(cfg), lastmod, 'weekly', '0.7', top_priority='0.8')
    for post in blog['posts']:
        # lastmod del articulo: su fecha de publicacion, no la del build. Un
        # articulo que no ha cambiado no debe pedir que lo reindexen cada vez.
        entries += group(post_paths(cfg, post), post['date'], 'yearly', '0.6', top_priority='0.7')

    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!--\n'
            '  Una entrada por idioma y por pagina: las cuatro homes, los cuatro\n'
            '  indices del blog y los cuatro idiomas de cada articulo. Cada una\n'
            '  repite el juego completo de hreflang, igual que el <head> de las\n'
            '  paginas: es la misma senal por dos vias.\n'
            '  Generado por _build/build.py; no editar a mano.\n'
            '-->\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
            '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + '\n'.join(entries) + '\n</urlset>\n')


# ------------------------------------------------------------- salida

def outputs(cfg, blog, template, lastmod):
    layout = layout_parts(template)
    files = {}
    for code in cfg['site']['order']:
        blocks = common_blocks(cfg, code, home_paths(cfg))
        data = cfg['langs'][code]
        blocks.update({
            'airbotMessages': json.dumps(
                {k: data['apps.airbot.' + k] for k in AIRBOT_KEYS},
                ensure_ascii=False, indent=2),
            'langHints': json.dumps(lang_hints(cfg, home_paths(cfg)),
                                    ensure_ascii=False, indent=2),
        })
        # Las tarjetas de la home enlazan al articulo: mismo slug, prefijo de
        # idioma de la pagina en la que estan.
        for post in blog['posts']:
            blocks['blog.%s.href' % post['id']] = post_paths(cfg, post)[code]
            blocks['blog.%s.date' % post['id']] = format_date(post['date'], code)
            blocks['blog.%s.dateIso' % post['id']] = post['date']
        files[rel_path(cfg['langs'][code]['path'])] = render(template, cfg, code, blocks)
        files.update(blog_files(cfg, blog, layout, code))

    files['sitemap.xml'] = sitemap(cfg, blog, lastmod)
    return files


def main():
    check = '--check' in sys.argv
    cfg = json.load(open(os.path.join(BUILD, 'i18n.json'), encoding='utf-8'))
    blog = json.load(open(os.path.join(BUILD, 'blog.json'), encoding='utf-8'))
    template = open(os.path.join(BUILD, 'template.html'), encoding='utf-8').read()

    existing_map = os.path.join(ROOT, 'sitemap.xml')
    if check and os.path.exists(existing_map):
        found = re.search(r'<lastmod>([\d-]+)</lastmod>', open(existing_map, encoding='utf-8').read())
        lastmod = found.group(1) if found else date.today().isoformat()
    else:
        lastmod = date.today().isoformat()

    files = outputs(cfg, blog, template, lastmod)

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
