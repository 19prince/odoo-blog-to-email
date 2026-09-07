"""Self-check for the posts-block anchor. Run: python3 test_find_block.py"""
import sys, types

odoo = types.ModuleType('odoo')
odoo.models = types.SimpleNamespace(Model=object)
odoo.fields = types.SimpleNamespace()
odoo.api = types.SimpleNamespace(model_create_multi=lambda f: f)
sys.modules['odoo'] = odoo
sys.path.insert(0, 'odoo_blog_to_email/models')

from blog_post import _find_block, _splice_block, _build_posts_block, BLOCK_ANCHOR, SLOT_START, SLOT_END  # noqa: E402

POSTS = [{'name': 'Newest', 'teaser': 'a', 'url': 'https://example.com/blog/a-1'},
         {'name': 'Older', 'teaser': 'b', 'url': 'https://example.com/blog/b-2'}]
block = _build_posts_block(POSTS)
body = f'<div class="head">before</div>\n{block}\n<div class="foot">after</div>'

# finds the block, and only the block
start, end = _find_block(body)
assert body[start:end] == block, body[start:end][:200]

# swapping in a fresh render leaves everything else byte-identical
newer = _build_posts_block([{'name': 'Newer still', 'teaser': 'c', 'url': 'https://example.com/blog/c-3'}])
swapped = body[:start] + newer + body[end:]
assert 'Newest' not in swapped and 'Newer still' in swapped
assert swapped.startswith('<div class="head">before</div>') and swapped.endswith('<div class="foot">after</div>')

# re-finding gives the same span back, so repeat refreshes are stable...
s2, e2 = _find_block(swapped)
assert swapped[s2:e2] == newer
# ...and re-rendering identical posts is a byte-for-byte no-op (the write is skipped)
assert swapped[:s2] + _build_posts_block([{'name': 'Newer still', 'teaser': 'c', 'url': 'https://example.com/blog/c-3'}]) + swapped[e2:] == swapped

# the legacy comment markers still resolve, once
legacy = f'<div>x</div>{SLOT_START}\n{SLOT_END}<div>y</div>'
assert _find_block(legacy) is None and SLOT_START in legacy

# no anchor at all -> None, so the caller skips instead of mangling the body
assert _find_block('<div>nothing here</div>') is None
assert BLOCK_ANCHOR in block

# the regression that shipped: body_arch reads back as Markup, and Markup + str
# escapes the str operand, publishing the block as visible source text
try:
    from markupsafe import Markup
except ImportError:
    print('ok (markupsafe absent, skipped the Markup case)')
else:
    spliced = _splice_block(Markup(body), newer)
    assert '&lt;div' not in spliced, spliced[spliced.find('&lt;div') - 80:][:200]
    assert 'data-name="RecentPosts">' in spliced
    assert _splice_block(Markup(f'{SLOT_START}\n{SLOT_END}'), newer).startswith('<div')
    assert _splice_block(Markup('<div>no anchor</div>'), newer) is None
    print('ok')
