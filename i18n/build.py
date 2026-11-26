#!/usr/bin/env python3
"""Builds the translated copies of this site.

The English pages at the top level are the source. Each language gets its own folder (/es/, /ru/, ...) with the
same pages, its text taken from i18n/<code>.json. Those files map every English text block to its translation; a
block that is missing stays English and is listed when you build.

    python3 i18n/build.py extract   # list the English text blocks in i18n/source.json (after editing a page)
    python3 i18n/build.py           # rebuild every language folder, the language menu and sitemap.xml

Needs Python 3 and beautifulsoup4 (pip install beautifulsoup4).
"""
import json, os, re, sys
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, NavigableString, Tag, Comment

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, 'i18n', 'config.json'), encoding='utf-8'))
BASE = CFG['base'].rstrip('/')
LANGS = CFG['languages']                       # [{code, name}], English first
CODES = [l['code'] for l in LANGS]
PAGES = CFG['pages']                           # [{src, menu}] menu = CSS selector the language menu goes into

INLINE = {'a', 'strong', 'em', 'b', 'i', 'code', 'small', 'br', 'abbr', 'time', 'kbd', 'sup', 'sub', 'span', 'mark', 'u'}
SKIP = {'script', 'style', 'svg', 'template', 'noscript'}
ATTRS = ('alt', 'aria-label', 'title', 'placeholder')
META = {('name', 'description'), ('property', 'og:title'), ('property', 'og:description'),
        ('name', 'twitter:title'), ('name', 'twitter:description')}
LD_KEYS = {'description', 'text'}
OG_LOCALE = {'en': 'en_US', 'es': 'es_ES', 'fr': 'fr_FR', 'de': 'de_DE', 'it': 'it_IT', 'pt': 'pt_BR', 'ru': 'ru_RU',
             'tr': 'tr_TR', 'hy': 'hy_AM', 'ja': 'ja_JP', 'ko': 'ko_KR', 'zh': 'zh_CN', 'id': 'id_ID', 'vi': 'vi_VN'}
HREFLANG = {'zh': 'zh-Hans'}


def norm(s):
    return re.sub(r'\s+', ' ', s).strip()


def page_path(src):
    """URL path of a page: index.html -> '/', privacy.html -> '/privacy.html', privacy/index.html -> '/privacy/'."""
    return '/' + re.sub(r'(^|/)index\.html$', r'\1', src)


def lang_url(code, src):
    return BASE + ('' if code == 'en' else '/' + code) + page_path(src)


def inline_only(el):
    return all(d.name in INLINE for d in el.descendants if isinstance(d, Tag))


def blocks(el, out):
    """Yield (kind, node, text): text blocks in reading order."""
    for c in list(el.children):
        if isinstance(c, Comment):
            continue
        if isinstance(c, NavigableString):
            if norm(c) and not inline_only(el):
                out.append(('text', c, norm(c)))
            continue
        if c.name in SKIP or c.has_attr('data-i18n-skip'):
            continue
        if inline_only(c) and norm(c.get_text()):
            out.append(('html', c, norm(c.decode_contents())))
        else:
            blocks(c, out)


def ld_strings(obj, out, parent_type=None):
    if isinstance(obj, dict):
        t = obj.get('@type')
        for k, v in obj.items():
            if isinstance(v, str) and (k in LD_KEYS or (k == 'name' and t == 'Question')):
                out.append((obj, k, v))
            else:
                ld_strings(v, out, t)
    elif isinstance(obj, list):
        for v in obj:
            ld_strings(v, out, parent_type)


def collect(soup):
    """All translatable strings of a page, with setters to replace them."""
    items = []
    if soup.title and soup.title.string:
        items.append((norm(soup.title.string), lambda t, n=soup.title: n.string.replace_with(t)))
    for m in soup.find_all('meta'):
        for k, v in META:
            if m.get(k) == v and m.get('content'):
                items.append((norm(m['content']), lambda t, m=m: m.__setitem__('content', t)))
    for s in soup.find_all('script', type='application/ld+json'):
        data = json.loads(s.string)
        found = []
        ld_strings(data, found)
        for obj, k, v in found:
            items.append((norm(v), lambda t, o=obj, k=k: o.__setitem__(k, t)))
        s['data-ld'] = '1'
        s._ld = data
    out = []
    blocks(soup.body, out)
    for kind, node, text in out:
        if kind == 'text':
            items.append((text, lambda t, n=node: n.replace_with(NavigableString(' ' + t + ' '))))
        else:
            def set_html(t, n=node):
                n.clear()
                frag = BeautifulSoup(t, 'html.parser')
                for x in list(frag.contents):
                    n.append(x)
            items.append((text, set_html))
    for el in soup.body.find_all(True):
        if el.name in SKIP and el.name != 'svg':
            continue
        if el.has_attr('data-i18n-skip') or el.find_parent(attrs={'data-i18n-skip': True}):
            continue
        for a in ATTRS:
            if el.get(a) and norm(el[a]):
                items.append((norm(el[a]), lambda t, e=el, a=a: e.__setitem__(a, t)))
        for a in list(el.attrs):
            if a.startswith('data-text-'):
                items.append((norm(el[a]), lambda t, e=el, a=a: e.__setitem__(a, t)))
    return [(k, f) for k, f in items if re.search(r'[A-Za-z]', k)]


def read(src):
    return open(os.path.join(ROOT, src), encoding='utf-8').read()


def extract():
    seen, order = set(), []
    for p in PAGES:
        for k, _ in collect(BeautifulSoup(read(p['src']), 'html.parser')):
            if k not in seen:
                seen.add(k)
                order.append(k)
    json.dump(order, open(os.path.join(ROOT, 'i18n', 'source.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(len(order), 'text blocks in i18n/source.json')


def head_block(src, code):
    links = ''.join(f'<link rel="alternate" hreflang="{HREFLANG.get(c, c)}" href="{lang_url(c, src)}">' for c in CODES)
    links += f'<link rel="alternate" hreflang="x-default" href="{lang_url("en", src)}">'
    js = ("<script>(function(){var L=%s;try{document.addEventListener('click',function(e){var a=e.target.closest&&"
          "e.target.closest('[data-lang]');if(a)localStorage.setItem('lang',a.getAttribute('data-lang'));});") % json.dumps(CODES)
    if code == 'en':
        # Send a first-time visitor to their own language once; a choice made in the menu always wins.
        js += ("var s=localStorage.getItem('lang');var n=((navigator.languages&&navigator.languages[0])||navigator.language||'')"
               ".toLowerCase().slice(0,2);var t=s||n;if(t&&t!=='en'&&L.indexOf(t)>-1){location.replace('/'+t+location.pathname+location.hash);}")
    js += '}catch(e){}})();</script>'
    return '<!-- i18n:head -->' + links + js + '<!-- /i18n:head -->'


def menu_block(src, code):
    cur = next(l for l in LANGS if l['code'] == code)
    items = ''.join(
        f'<li><a href="{urlparse(lang_url(l["code"], src)).path}" hreflang="{HREFLANG.get(l["code"], l["code"])}" lang="{l["code"]}" '
        f'data-lang="{l["code"]}"{" aria-current=\"true\"" if l["code"] == code else ""}>{l["name"]}</a></li>' for l in LANGS)
    globe = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm6.9 6h-2.9a15.7 15.7 0 0 0-1.4-3.6A8 8 0 0 1 18.9 8ZM12 4c.8 1.2 1.5 2.5 1.9 4h-3.8c.4-1.5 1.1-2.8 1.9-4ZM4.3 14a8.2 8.2 0 0 1 0-4h3.4a16.5 16.5 0 0 0 0 4H4.3Zm.8 2h2.9c.3 1.3.8 2.5 1.4 3.6A8 8 0 0 1 5.1 16ZM8 8H5.1a8 8 0 0 1 4.3-3.6C8.8 5.5 8.3 6.7 8 8Zm4 12c-.8-1.2-1.5-2.5-1.9-4h3.8c-.4 1.5-1.1 2.8-1.9 4Zm2.3-6H9.7a14.7 14.7 0 0 1 0-4h4.6a14.7 14.7 0 0 1 0 4Zm.3 5.6c.6-1.1 1.1-2.3 1.4-3.6h2.9a8 8 0 0 1-4.3 3.6Zm1.7-5.6a16.5 16.5 0 0 0 0-4h3.4a8.2 8.2 0 0 1 0 4h-3.4Z"/></svg>')
    return (f'<!-- i18n:menu --><details class="lang-menu" data-i18n-skip><summary aria-label="Language: {cur["name"]}">{globe}'
            f'<span>{code.upper()}</span></summary><ul>{items}</ul></details><!-- /i18n:menu -->')


def bust(html, src):
    """Add ?v=<content hash> to local .css/.js links so browsers fetch a changed file instead of a cached one."""
    import hashlib
    def rep(m):
        attr, path = m.group(1), m.group(2)
        f = os.path.normpath(os.path.join(ROOT, os.path.dirname(src), path))
        if not os.path.exists(f):
            return m.group(0)
        h = hashlib.sha1(open(f, 'rb').read()).hexdigest()[:8]
        return f'{attr}="{path}?v={h}"'
    return re.sub(r'(href|src)="((?![a-z]+:|/)[^"?#]+\.(?:css|js))(?:\?v=[0-9a-f]+)?"', rep, html)


def put_blocks(html, src, code, menu_sel):
    """Insert or refresh the marked head and menu blocks in raw HTML (keeps the rest of the file byte for byte)."""
    html = re.sub(r'\s*<!-- i18n:head -->.*?<!-- /i18n:head -->', '', html, flags=re.S)
    html = re.sub(r'<!-- i18n:menu -->.*?<!-- /i18n:menu -->', '<!-- i18n:menu-slot -->', html, flags=re.S)
    html = bust(html, src)
    html = html.replace('</head>', '  ' + head_block(src, code) + '\n</head>', 1)
    if '<!-- i18n:menu-slot -->' not in html:
        raise SystemExit(f'{src}: add <!-- i18n:menu --><!-- /i18n:menu --> where the language menu goes ({menu_sel})')
    return html.replace('<!-- i18n:menu-slot -->', menu_block(src, code), 1)


def rewrite_urls(soup, src, code):
    pages = {page_path(p['src']) for p in PAGES}
    here = page_path(src)
    for el in soup.find_all(True):
        for a in ('href', 'src', 'srcset'):
            v = el.get(a)
            if not v or el.name == 'link' and el.get('rel') in (['alternate'],):
                continue
            u = urlparse(v)
            if u.scheme in ('mailto', 'tel', 'data', 'javascript') or v.startswith('#'):
                continue
            if u.scheme in ('http', 'https') or v.startswith('//'):
                if BASE.split('//')[1] == u.netloc and u.path in pages:
                    el[a] = BASE + '/' + code + u.path + (('#' + u.fragment) if u.fragment else '')
                continue
            if v.startswith('/'):
                if urlparse(v).path in pages and not v.startswith('/' + code + '/'):
                    el[a] = '/' + code + v
                continue
            target = urlparse(urljoin(here, v)).path
            if target not in pages:
                el[a] = '../' + v


def build():
    tr = {}
    for c in CODES[1:]:
        f = os.path.join(ROOT, 'i18n', c + '.json')
        tr[c] = json.load(open(f, encoding='utf-8')) if os.path.exists(f) else {}
    missing = {c: set() for c in CODES[1:]}
    for p in PAGES:
        src = p['src']
        en_html = put_blocks(read(src), src, 'en', p['menu'])
        open(os.path.join(ROOT, src), 'w', encoding='utf-8').write(en_html)
        for code in CODES[1:]:
            soup = BeautifulSoup(read(src), 'html.parser')
            for key, setter in collect(soup):
                t = tr[code].get(key)
                if t is None:
                    missing[code].add(key)
                else:
                    setter(t)
            for s in soup.find_all('script', attrs={'data-ld': '1'}):
                data = s._ld
                if isinstance(data, dict) and 'inLanguage' in data:
                    data['inLanguage'] = CODES
                s.string = json.dumps(data, ensure_ascii=False, indent=2)
                del s['data-ld']
            soup.html['lang'] = HREFLANG.get(code, code)
            for l in soup.find_all('link', rel='canonical'):
                l['href'] = lang_url(code, src)
            for m in soup.find_all('meta', property='og:url'):
                m['content'] = lang_url(code, src)
            og = soup.find('meta', property='og:locale')
            if og:
                og['content'] = OG_LOCALE.get(code, code)
            rewrite_urls(soup, src, code)
            out = str(soup)
            out = re.sub(r'<!-- i18n:head -->.*?<!-- /i18n:head -->', lambda m: head_block(src, code), out, flags=re.S)
            out = re.sub(r'<!-- i18n:menu -->.*?<!-- /i18n:menu -->', lambda m: menu_block(src, code), out, flags=re.S)
            dest = os.path.join(ROOT, code, src)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            open(dest, 'w', encoding='utf-8').write(out)
    # Sitemap with every language version of every page.
    urls = []
    for p in PAGES:
        alts = ''.join(f'\n    <xhtml:link rel="alternate" hreflang="{HREFLANG.get(c, c)}" href="{lang_url(c, p["src"])}"/>' for c in CODES)
        for c in CODES:
            urls.append(f'  <url>\n    <loc>{lang_url(c, p["src"])}</loc>{alts}\n  </url>')
    open(os.path.join(ROOT, 'sitemap.xml'), 'w', encoding='utf-8').write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' + '\n'.join(urls) + '\n</urlset>\n')
    for c, keys in missing.items():
        if keys:
            print(f'{c}: {len(keys)} blocks still in English')
    print('built', len(CODES) - 1, 'languages x', len(PAGES), 'pages')


if __name__ == '__main__':
    extract() if sys.argv[1:] == ['extract'] else build()
