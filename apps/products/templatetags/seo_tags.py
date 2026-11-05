import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

# [metin](/relatif/yol/)  veya  [metin](https://...)
_LINK_RE = re.compile(r"\[([^\]]+)\]\((/[^)\s]*|https?://[^)\s]+)\)")


@register.filter
def render_description(value):
    """
    Ürün açıklamasını güvenli HTML'e çevirir.

    Önce HER ŞEY escape edilir (admin'e HTML yazılsa bile çalışmaz); sonra sadece
    şu basit biçimler HTML'e dönüşür:
      - boş satırla ayrılan bloklar  -> <p>
      - "## Başlık" ile başlayan blok -> <h2>
      - [metin](/yol/)               -> <a href="/yol/">metin</a>
    """
    if not value:
        return ""
    out = []
    for block in re.split(r"\n\s*\n", str(value).replace("\r\n", "\n").strip()):
        block = block.strip()
        if not block:
            continue
        is_h2 = block.startswith("## ")
        text = escape(block[3:] if is_h2 else block)
        text = _LINK_RE.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
        text = text.replace("\n", "<br>")
        out.append(f"<h2>{text}</h2>" if is_h2 else f"<p>{text}</p>")
    return mark_safe("\n".join(out))
