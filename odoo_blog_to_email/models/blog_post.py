import html
import logging
import re

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

PARAM_MAILING_ID = 'odoo_blog_to_email.auto_mailing_id'
PARAM_TAG        = 'odoo_blog_to_email.auto_mailing_tag'
PARAM_COUNT      = 'odoo_blog_to_email.auto_mailing_post_count'
PARAM_STATUS     = 'odoo_blog_to_email.last_refresh'

SLOT_START = '<!-- BLOG_POSTS_SLOT:START -->'   # legacy anchor, honoured once then replaced
SLOT_END   = '<!-- BLOG_POSTS_SLOT:END -->'
BLOCK_ANCHOR = 'data-name="RecentPosts"'

# Any of these changing can change what the block should say.
WATCHED_FIELDS = {'is_published', 'tag_ids', 'name', 'teaser', 'post_date', 'blog_id', 'active'}

MONO = "'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace"
SANS = "'Inter Tight', -apple-system, BlinkMacSystemFont, system-ui, sans-serif"

LABELS = [
    '01 &nbsp;&middot;&nbsp; LATEST',
    '02 &nbsp;&middot;&nbsp; PREVIOUS',
    '03 &nbsp;&middot;&nbsp; EARLIER',
    '04 &nbsp;&middot;&nbsp; RECENT',
    '05 &nbsp;&middot;&nbsp; RECENT',
]


def _clean_teaser(raw, title):
    text = re.sub(r'[​‌‍﻿]+', ' ', raw or '')
    text = re.sub(r'\s+', ' ', text).strip()
    if text.startswith(title):
        text = text[len(title):].strip()
    text = re.sub(r'^[A-Z][a-z]+ \d{1,2},?\s+\d{4}\s*', '', text).strip()
    text = re.sub(r'^TL;DR\s*', '', text, flags=re.IGNORECASE).strip()
    if len(text) > 160:
        text = text[:160].rsplit(' ', 1)[0] + '...'
    return text or 'Read the full post on the blog.'


def _render_slot(index, title, teaser, url, is_last, labels):
    label = labels[index] if index < len(labels) else f'{index + 1:02d} &nbsp;&middot;&nbsp; RECENT'
    safe_url = html.escape(url)

    if is_last:
        cell_style = 'padding-top: 24px;'
    elif index == 0:
        cell_style = 'padding-bottom: 24px; border-bottom: 1px solid #e9edf3;'
    else:
        cell_style = 'padding: 24px 0; border-bottom: 1px solid #e9edf3;'

    safe_title  = html.escape(title)
    safe_teaser = html.escape(teaser)

    return (
        f'        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse: collapse;">\n'
        f'            <tr>\n'
        f'                <td style="{cell_style}">\n'
        f'                    <p style="font-family: {MONO}; font-size: 10px; font-weight: 500; letter-spacing: .12em; text-transform: uppercase; color: #a9b3c2; margin: 0 0 8px 0;">{label}</p>\n'
        f'                    <p style="font-family: {SANS}; font-weight: 700; font-size: 18px; line-height: 1.2; letter-spacing: -0.02em; color: #071222; margin: 0 0 8px 0;">{safe_title}</p>\n'
        f'                    <p style="font-family: {SANS}; font-weight: 400; font-size: 14px; line-height: 1.55; color: #525c6d; margin: 0 0 12px 0;">{safe_teaser}</p>\n'
        f'                    <a href="{safe_url}" style="font-family: {SANS}; font-size: 13px; font-weight: 600; color: #EA6C08; text-decoration: none; letter-spacing: -0.01em;">Read &#8594;</a>\n'
        f'                </td>\n'
        f'            </tr>\n'
        f'        </table>\n'
    )


def _find_block(body):
    """Byte span of the generated posts block, located by its data-name attribute.

    ponytail: the mailing editor drops HTML comments when the body is saved, so
    the old <!-- BLOG_POSTS_SLOT --> anchors vanished on the module's own first
    refresh and every later one silently skipped. data-name survives - the
    snippet system depends on it, and body_arch's sanitiser keeps every
    attribute. Ceiling: a naive <div>/</div> depth count, fine because the block
    we emit is well-formed; reach for lxml if it ever wraps pasted raw HTML.
    """
    pos = body.find(BLOCK_ANCHOR)
    if pos == -1:
        return None
    start = body.rfind('<div', 0, pos)
    if start == -1:
        return None
    depth, i = 0, start
    while i < len(body):
        if body.startswith('<div', i):
            depth += 1
            i += 4
        elif body.startswith('</div>', i):
            depth -= 1
            i += 6
            if depth == 0:
                return start, i
        else:
            i += 1
    return None


def _splice_block(body, posts_block):
    """Body with the posts block swapped in, or None when there is no anchor.

    ponytail: str(body) is load-bearing. body_arch reads back as Markup, and
    Markup + str escapes the str operand - which published the block as visible
    page source instead of markup. Keep the whole splice in plain str; the ORM
    sanitises on write.
    """
    body = str(body or '')
    span = _find_block(body)
    if span:
        return body[:span[0]] + posts_block + body[span[1]:]
    if SLOT_START in body and SLOT_END in body:
        # Legacy body whose comment markers are still intact. The block we write
        # carries its own data-name anchor, so this runs at most once.
        return re.sub(f'{re.escape(SLOT_START)}.*?{re.escape(SLOT_END)}',
                      posts_block, body, flags=re.DOTALL)
    return None


def _html_body(body):
    """The body_html twin of an arch body: no empty <style>/<script> left to self-close.

    ponytail: body_html declares sanitize='email_outgoing', which quietly sets
    sanitize_output_method='xml' (odoo/fields.py) - so the mail editor's empty
    <style id="design-element"></style> is written back as <style/>. body_arch
    escapes this only because it passes sanitize_output_method="html" of its own.
    HTML5 parsers do not honour a self-closed <style>: it opens RAWTEXT and
    swallows the rest of the document, so Gmail rendered the whole mailing
    blank while the text/plain part came through intact. Padding the element
    denies the serialiser anything to self-close. Only <style> and <script>
    matter - every other empty element self-closes harmlessly.
    """
    return re.sub(r'<(style|script)\b([^>]*)>\s*</\1\s*>',
                  r'<\1\2>/**/</\1>', body, flags=re.IGNORECASE)

def _build_posts_block(posts):
    """posts: list of dicts with 'name', 'teaser' and an absolute 'url'."""
    slots = []
    for i, post in enumerate(posts):
        title = post.get('name') or ''
        slots.append(_render_slot(
            i, title, _clean_teaser(post.get('teaser') or '', title), post.get('url') or '#',
            is_last=(i == len(posts) - 1), labels=LABELS,
        ))

    inner = '\n'.join(slots)
    return (
        f'<div class="s_text_block o_mail_snippet_general" style="background-color: #ffffff; padding: 0 32px 40px;" data-snippet="s_text_block" {BLOCK_ANCHOR}>\n'
        f'    <div class="container s_allow_columns">\n\n'
        f'        <hr style="border: 0; border-top: 1px solid #d3dae4; margin: 0 0 32px 0;">\n\n'
        f'        <p style="font-family: {MONO}; font-size: 11px; font-weight: 500; letter-spacing: .16em; text-transform: uppercase; color: #5DA9FF; margin: 0 0 28px 0;">RECENT POSTS</p>\n\n'
        f'{inner}'
        f'    </div>\n'
        f'</div>'
    )


class BlogPost(models.Model):
    _inherit = 'blog.post'

    @api.model_create_multi
    def create(self, vals_list):
        posts = super().create(vals_list)
        posts._obte_sync()
        return posts

    def write(self, vals):
        result = super().write(vals)
        if WATCHED_FIELDS & set(vals):
            self._obte_sync()
        return result

    def unlink(self):
        result = super().unlink()
        self._obte_sync()          # self is empty now; the refresh only needs self.env
        return result

    def _obte_sync(self):
        """Re-render on anything that could change the block.

        ponytail: no transition detection. The old version fired only on an
        unpublished -> published flip, so tagging a post that was already live,
        renaming one, or unpublishing a listed one all left the mailing stale.
        Firing on every watched change is correct because the refresh is a
        no-op when the rendered block is unchanged.
        """
        if self.env.context.get('_obte_auto_refresh'):
            return
        self.with_context(_obte_auto_refresh=True)._refresh_auto_mailing()

    def _obte_note(self, message, warn=False):
        """Log, and leave the same line where Settings can show it."""
        (_logger.warning if warn else _logger.info)('odoo_blog_to_email: %s', message)
        self.env['ir.config_parameter'].sudo().set_param(
            PARAM_STATUS, f'{fields.Datetime.now()} UTC — {message}')

    def _refresh_auto_mailing(self):
        """Re-render the Recent Posts block in the configured mailing.

        Safe to call as often as you like: it writes only when the rendered
        block differs from what the mailing already holds.
        """
        get_param = self.env['ir.config_parameter'].sudo().get_param

        mailing_id_str = get_param(PARAM_MAILING_ID)
        if not mailing_id_str:
            return self._obte_note('no mailing configured in Settings', warn=True)
        try:
            mailing_id = int(mailing_id_str)
        except (TypeError, ValueError):
            return self._obte_note(f'invalid mailing id {mailing_id_str!r}', warn=True)

        try:
            post_count = int(get_param(PARAM_COUNT) or 3)
        except (TypeError, ValueError):
            post_count = 3
        tag_name = (get_param(PARAM_TAG) or 'Newsletter').lower()

        mailing = self.env['mailing.mailing'].sudo().browse(mailing_id)
        if not mailing.exists():
            return self._obte_note(f'mailing {mailing_id} no longer exists', warn=True)

        posts = self.env['blog.post'].sudo().search(
            [('is_published', '=', True), ('tag_ids.name', '=ilike', tag_name)],
            order='post_date desc',
            limit=post_count,
        )
        if not posts:
            return self._obte_note(f'no published posts tagged {tag_name!r}', warn=True)

        # get_base_url() resolves the post's own website domain, falling back to
        # web.base.url - which on a hosted instance is the *.odoo.com hostname.
        posts_block = _build_posts_block([{
            'name': post.name,
            'teaser': post.teaser,
            'url': post.get_base_url().rstrip('/') + (post.website_url or '/'),
        } for post in posts])

        body = str(mailing.body_arch or '')
        new_body = _splice_block(body, posts_block)
        if new_body is None:
            return self._obte_note(
                f'no RecentPosts block in mailing {mailing_id} ({mailing.subject!r})', warn=True)

        if new_body == body:
            return self._obte_note(f'already current — {len(posts)} post(s)')

        mailing.sudo().write({'body_arch': new_body, 'body_html': _html_body(new_body)})
        self._obte_note(f'refreshed {mailing.subject!r} with {len(posts)} post(s)')
