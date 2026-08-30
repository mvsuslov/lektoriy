"""Markdown → HTML с формулами (MathML). Серверный рендер — клиенту не нужен JS."""
import re
import markdown
import bleach
from latex2mathml.converter import convert as latex_to_mathml

ALLOWED_TAGS = list(bleach.sanitizer.ALLOWED_TAGS) + [
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "br", "hr", "span", "div",
    "table", "thead", "tbody", "tr", "th", "td", "caption",
    "img", "figure", "figcaption", "pre", "code", "blockquote",
    "sup", "sub", "del", "em", "strong", "ul", "ol", "li", "a",
    # MathML
    "math", "semantics", "mrow", "mi", "mo", "mn", "mtext", "msup",
    "msub", "msubsup", "mfrac", "msqrt", "mroot", "munder", "mover",
    "munderover", "mtable", "mtr", "mtd", "mspace", "mpadded",
    "mstyle", "ms", "mphantom", "menclose", "annotation",
]
ALLOWED_ATTRS = {
    **bleach.sanitizer.ALLOWED_ATTRIBUTES,
    "*": ["class", "style", "id"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height", "loading"],
    "math": ["xmlns", "display"],
    "annotation": ["encoding"],
    "mtd": ["columnalign", "rowalign"],
    "mtable": ["columnalign", "rowalign", "columnspacing", "rowspacing"],
}

MATH_BLOCK_RE = re.compile(r"\$\$([\s\S]+?)\$\$")
MATH_INLINE_RE = re.compile(r"(?<![\\$])\$(?!\$)([^$\n]+?)\$(?!\$)")


def _latex_to_mathml(latex: str, display: bool) -> str:
    try:
        ml = latex_to_mathml(latex.strip())
        if display:
            # оборачиваем в блочный контейнер
            return f'<div class="math-display">{ml}</div>'
        return f'<span class="math-inline">{ml}</span>'
    except Exception:
        return f'<code class="math-error">{latex}</code>'


def render_md(text: str) -> str:
    """Markdown + $...$/$$...$$ → безопасный HTML с MathML."""
    if not text:
        return ""

    # 1) Защищаем формулы плейсхолдерами
    stash = []

    def stash_math(m, display):
        key = f"\x00MATH{len(stash)}\x00"
        stash.append(_latex_to_mathml(m.group(1), display))
        return key

    t = MATH_BLOCK_RE.sub(lambda m: stash_math(m, True), text)
    t = MATH_INLINE_RE.sub(lambda m: stash_math(m, False), t)

    # 2) Markdown → HTML
    html = markdown.markdown(
        t,
        extensions=["extra", "sane_lists", "pymdownx.tilde"],
        output_format="html5",
    )

    # 3) Возвращаем формулы
    for i, mhtml in enumerate(stash):
        html = html.replace(f"\x00MATH{i}\x00", mhtml)

    # 4) Bleach — безопасность
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS,
                        strip=True)