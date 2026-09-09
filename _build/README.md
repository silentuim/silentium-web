# _build — fuente de verdad del sitio

Los cuatro `index.html` publicados (`/`, `/en/`, `/fr/`, `/de/`), las paginas
del blog (`/blog/`, `/en/blog/`, ... y un directorio por articulo) y el
`sitemap.xml` son **archivos generados**. No se editan a mano: se generan desde
aqui, y asi los cuatro idiomas no pueden desincronizarse.

Esta carpeta empieza por `_`, asi que Jekyll (activo por defecto en GitHub
Pages) no la publica. Vive en el repositorio, pero no en el sitio.

## Cambiar algo

| Que quiero cambiar | Donde se toca |
|---|---|
| Un precio, un enlace de Stripe, la estructura, el CSS | `template.html` |
| Un texto traducible, el `<title>`, la descripcion, el Open Graph | `i18n.json` |
| El titulo, el tag o el extracto de un articulo | `i18n.json` (`blog.postN.*`) |
| El cuerpo de un articulo, su slug o su fecha | `blog.json` |
| Anadir un idioma | `i18n.json` (`site.order` + un bloque en `langs`) y `FLAGS` en `build.py` |

Despues, siempre:

    python3 _build/build.py

Sin dependencias: solo Python 3.

## Comprobar que nada se ha ido de las manos

    python3 _build/build.py --check

No escribe nada. Sale con codigo 1 si algun archivo publicado no coincide con lo
que la plantilla generaria, que es la senal de que alguien edito un HTML
generado a mano o de que falta ejecutar el build. Util como gancho de
pre-commit.

## Por que no hay redireccion automatica por idioma

Googlebot ejecuta JavaScript y renderiza en `en-US`. Una redireccion basada en
`navigator.language` en `/` mandaria tambien al rastreador a `/en/`, que es
exactamente el problema que esta reestructuracion viene a resolver. En su lugar,
la primera visita sin preferencia guardada ve un aviso que **sugiere** el idioma
del navegador con un enlace normal. Cada URL sirve siempre su idioma, para
cualquier visitante, humano o rastreador.

## El blog

Cada articulo se publica en `/blog/<slug>/` y en `/<idioma>/blog/<slug>/`. El
slug es **uno solo, en ingles, igual en los cuatro idiomas**: asi cambiar de
idioma dentro de un articulo no cambia la URL mas que en el prefijo, y el
selector del cabecero puede llevarte al mismo articulo en otra lengua en vez de
devolverte a la home.

Un articulo esta partido en dos archivos a proposito:

- `i18n.json` guarda `blog.postN.tag`, `.title` y `.desc`. Son los mismos textos
  que ya pintaban las tarjetas de la home, y ahora tambien el indice y la
  cabecera del articulo. Una sola copia, cuatro sitios donde sale.
- `blog.json` guarda lo que es solo del articulo: `slug`, `date` y `body`.

El `body` es **texto plano, sin HTML**, en bloques: `## ` es un `<h2>`, un
bloque cuyas lineas empiezan por `- ` es una lista, y el resto son parrafos.
Todo se escapa al generar, asi que un articulo no puede colar marcado en la
pagina; los nombres de producto los envuelve `build.py` en
`<span translate="no">` por su cuenta.

Las plantillas `blog-index.html` y `blog-post.html` no repiten el diseno: piden
`{{styles}}`, `{{siteTop}}` y `{{siteFooter}}`, y `build.py` los recorta de
`template.html`. Tocar un color o anadir un enlace al menu sigue siendo un
cambio en un unico archivo.

Las paginas del blog no llevan JavaScript: ni el aviso de idioma ni la descarga
de AirBot pintan nada ahi. El aviso solo tiene sentido en la primera visita, que
casi siempre cae en la home, y quien llega a un articulo ya tiene el selector de
idioma completo en la cabecera.
