# -*- coding: utf-8 -*-
{
    'name': "Sistem Operasional dan Reservasi Terintegrasi Classico Coffee & Bake",
    'summary': 'Sistem Operasional dan Reservasi Terintegrasi untuk Classico Coffee & Bake',
    'description': '''
        Sistem terintegrasi yang menggantikan koordinasi manual berbasis WhatsApp dengan:
        - Manajemen Reservasi Pelanggan
        - Dashboard Kapasitas Meja Real-time
        - Laporan Shift Digital
        - Ticketing Keluhan Pelanggan
        - Pusat Dokumentasi Operasional
    ''',
    'sequence': -100,
    'author': "K02-G12",
    'category': 'Operations/Restaurant',
    'version': '1.0',
    'depends': ['base', 'mail', 'bus'],
    'assets': {
        'web.assets_backend': [
            'Sistem-Operasional-dan-Reservasi-Terintegrasi-Classico-Coffee-&-Bake/static/src/js/table_bus_service.js',
        ],
    },
    'data': [
        'data/ir_sequence.xml',
        'security/ir.model.access.csv',
        'views/menus.xml',
        'views/user_role_views.xml',
        'views/reservation_views.xml',
        'views/table_views.xml',
        'views/shift_views.xml',
        'views/complaint_views.xml',
        'views/operational_note_views.xml',
        'views/evaluation_report_template.xml',
        'views/evaluation_report_views.xml',
        'views/archive_views.xml',
        'wizard/evaluation_report_wizard_views.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
        'demo/operational_notes_demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
