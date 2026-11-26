# hoppyblocks.com

Website for hoppyblocks.com, served by GitHub Pages from the main branch.

## Languages

The English pages at the top level are the source. Every other language lives in its own folder (`/ru/`, `/hy/`, …)
and is generated, so don't edit those folders by hand.

- To change text: edit the English page, run `python3 i18n/build.py extract`, then add the new or changed English text
  with its translation to each `i18n/<code>.json` file.
- To rebuild every language, the language menu and `sitemap.xml`: `python3 i18n/build.py` (needs
  `pip install beautifulsoup4`). It lists any text that is still in English.
- Languages and pages are set in `i18n/config.json`.

First-time visitors whose browser language is one of these are sent to their language once; a choice made in the
language menu is remembered.
