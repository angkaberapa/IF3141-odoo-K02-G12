# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ClassicoTable(models.Model):
    _name = 'classico.table'
    _description = 'Dashboard Kapasitas Meja'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # FR-02: Sistem dapat memperbarui dashboard kapasitas meja
    name = fields.Char(
        string='Nomor Meja',
        required=True,
        tracking=True
    )
    
    capacity = fields.Integer(
        string='Kapasitas',
        required=True,
        default=2,
        tracking=True,
        help='Jumlah kursi pada meja'
    )
    
    state = fields.Selection([
        ('available', 'Tersedia'),
        ('occupied', 'Terisi'),
        ('reserved', 'Dipesan')
    ], string='Status', default='available', required=True, tracking=True)
    
    floor_section = fields.Selection([
        ('indoor', 'Indoor'),
        ('outdoor', 'Outdoor'),
        ('vip', 'VIP Area')
    ], string='Area', default='indoor', tracking=True)
    
    current_reservation_id = fields.Many2one(
        'classico.reservation',
        string='Reservasi Aktif',
        readonly=True
    )
    
    notes = fields.Text(
        string='Catatan',
        help='Catatan khusus mengenai meja (misal: dekat jendela, akses kursi roda)'
    )
    
    last_updated = fields.Datetime(
        string='Terakhir Diperbarui',
        readonly=True,
        default=fields.Datetime.now
    )
    
    updated_by = fields.Many2one(
        'res.users',
        string='Diperbarui Oleh',
        readonly=True
    )

    # QR-6: Ketepatan Data Kapasitas - Akurasi 100%
    _sql_constraints = [
        ('unique_table_name', 'UNIQUE(name)', 'Nomor meja sudah ada!')
    ]

    @api.constrains('capacity')
    def _check_capacity(self):
        for record in self:
            if record.capacity <= 0:
                raise ValidationError('Kapasitas meja harus lebih dari 0')
            if record.capacity > 20:
                raise ValidationError('Kapasitas meja tidak boleh lebih dari 20')

    def action_set_available(self):
        """Set meja menjadi tersedia"""
        self.write({
            'state': 'available',
            'current_reservation_id': False,
            'last_updated': fields.Datetime.now(),
            'updated_by': self.env.user.id
        })
        return True

    def action_set_occupied(self):
        """Set meja menjadi terisi"""
        self.write({
            'state': 'occupied',
            'last_updated': fields.Datetime.now(),
            'updated_by': self.env.user.id
        })
        return True

    def action_set_reserved(self):
        """Set meja menjadi dipesan"""
        self.write({
            'state': 'reserved',
            'last_updated': fields.Datetime.now(),
            'updated_by': self.env.user.id
        })
        return True

    @api.model
    def get_table_statistics(self):
        """Menghitung statistik meja untuk dashboard"""
        total = self.search_count([])
        available = self.search_count([('state', '=', 'available')])
        occupied = self.search_count([('state', '=', 'occupied')])
        reserved = self.search_count([('state', '=', 'reserved')])
        
        return {
            'total': total,
            'available': available,
            'occupied': occupied,
            'reserved': reserved,
            'availability_rate': (available / total * 100) if total > 0 else 0
        }
