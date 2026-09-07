{
    'name': 'Odoo Blog to Email',
    'version': '19.0.3.0.1',
    'category': 'Email Marketing',
    'summary': 'Refreshes a mailing when a tagged blog post is published. Configurable in Settings.',
    'author': '19 Prince',
    'website': 'https://www.19prince.com',
    'license': 'LGPL-3',
    'depends': ['website_blog', 'mass_mailing'],
    'data': [
        'data/mailing_starter.xml',
        'data/blog_to_email_cron.xml',
        'views/res_config_settings_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'auto_install': False,
}
