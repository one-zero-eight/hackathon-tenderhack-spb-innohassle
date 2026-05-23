"""SERP DOM scripts for CloakBrowser (scroll + product card extraction)."""

from __future__ import annotations

WB_BATCH_PAUSE_SEC = (0.7, 1.3)
WB_SCROLL_PAUSE_SEC = (0.45, 0.85)

CARDS_READY_SCRIPT = (
    "() => document.querySelectorAll('article, .product-card, [data-nm-id]').length > 0"
)

WB_CARD_COUNT_SCRIPT = (
    "() => document.querySelectorAll('article, .product-card, [data-nm-id]').length"
)

WB_SCROLL_JS = """
() => {
  const cards = document.querySelectorAll(
    '.product-card__wrapper, article.product-card, article[data-nm-id], [data-nm-id]'
  );
  const last = cards[cards.length - 1];
  if (last) {
    last.scrollIntoView({ block: 'end', behavior: 'instant' });
  } else {
    window.scrollBy(0, Math.max(window.innerHeight * 0.9, 900));
  }
  window.dispatchEvent(new Event('scroll'));
  const list = document.querySelector(
    '.product-list, .catalog-page__content, .catalog-page, main'
  );
  if (list && list.scrollHeight > list.clientHeight + 40) {
    list.scrollTop = list.scrollHeight;
  }
}
"""

WB_EXTRACT_ALL_CARDS_JS = """
() => {
  const pickText = (root, sel) => {
    const el = root.querySelector(sel);
    return el ? el.innerText.trim() : null;
  };
  const pickAttr = (root, sel, attr) => {
    const el = root.querySelector(sel);
    if (!el) return null;
    return el.getAttribute(attr) || null;
  };
  const pickPrice = (card) => {
    const sels = [
      'ins.price__lower-price',
      '.price__lower-price',
      '.product-card__price',
      '.price__wrap',
      "span[class*='price__lower']",
      "span[class*='price']",
    ];
    for (const sel of sels) {
      const el = card.querySelector(sel);
      if (el) {
        const t = el.innerText.trim();
        if (/\\d/.test(t)) return t;
      }
    }
    const m = (card.innerText || '').match(/(\\d[\\d\\s\\u00a0]*)\\s*₽/);
    return m ? m[0].trim() : null;
  };
  const pickOriginalPrice = (card) => {
    const el = card.querySelector(
      "del, .price__old, .product-card__price-old, span[class*='price-old'], span[class*='old-price']"
    );
    if (!el) return null;
    const t = el.innerText.trim();
    return /\\d/.test(t) ? t : null;
  };
  const cards = document.querySelectorAll('article, .product-card, [data-nm-id]');
  const out = [];
  for (const card of cards) {
    const priceText = pickPrice(card);
    let name = pickText(card, ".product-card__name, .goods-name, [class*='product-card__name']");
    if (name) name = name.replace(/^\\//, '').trim();
    out.push({
      name,
      brand: pickText(card, ".product-card__brand, .brand-name, [class*='brand']"),
      priceText,
      originalPriceText: pickOriginalPrice(card),
      url: pickAttr(card, "a.product-card__link, a[href*='/catalog/']", 'href'),
      image_url: pickAttr(card, 'img', 'src') || pickAttr(card, 'img', 'data-src'),
    });
  }
  return out;
}
"""
