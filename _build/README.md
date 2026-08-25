# _build — fuente de verdad del sitio

Los cuatro `index.html` publicados (`/`, `/en/`, `/fr/`, `/de/`) y el
`sitemap.xml` son **archivos generados**. No se editan a mano: se generan desde
aqui, y asi los cuatro idiomas no pueden desincronizarse.

Esta carpeta empieza por `_`, asi que Jekyll (activo por defecto en GitHub
Pages) no la publica. Vive en el repositorio, pero no en el sitio.

## Cambiar algo

| Que quiero cambiar | Donde se toca |
|---|---|
| Un precio, un enlace de Stripe, la estructura, el CSS | `template.html` |
| Un texto traducible, el `<title>`, la descripcion, el Open Graph | `i18n.json` |
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
