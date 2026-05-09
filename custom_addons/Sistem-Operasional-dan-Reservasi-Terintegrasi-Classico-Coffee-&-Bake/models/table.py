# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ClassicoTable(models.Model):
    _name = 'classico.table'
    _description = 'Dashboard Kapasitas Meja'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    _table_bus_channel = 'classico_table_status'

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
        ('reserved', 'Dipesan'),
        ('unavailable', 'Tidak Tersedia')
    ], string='Status', default='available', required=True, tracking=True)
    
    floor_section = fields.Selection([
        ('indoor', 'Indoor'),
        ('outdoor', 'Outdoor'),
        ('vip', 'VIP Area')
    ], string='Area', default='indoor', tracking=True)
    
    current_reservation_id = fields.Many2one(
        'classico.reservation',
        string='Reservasi Aktif',
        compute='_compute_current_reservation',
        store=False
    )

    active_allocation_id = fields.Many2one(
        'classico.table.allocation',
        string='Alokasi Aktif',
        compute='_compute_current_reservation',
        store=False
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

    def _compute_current_reservation(self):
        now = fields.Datetime.now()
        for record in self:
            allocation = self.env['classico.table.allocation'].search([
                ('table_id', '=', record.id),
                ('state', '=', 'active'),
                ('start_datetime', '<=', now),
                ('end_datetime', '>=', now),
                ('reservation_id.state', 'in', ['confirmed', 'arrived']),
            ], limit=1)
            record.active_allocation_id = allocation
            record.current_reservation_id = allocation.reservation_id

    # QR-6: Ketepatan Data Kapasitas - Akurasi 100%
    _sql_constraints = [
        ('unique_table_name', 'UNIQUE(name)', 'Nomor meja sudah ada!')
    ]

    def write(self, vals):
        notify_status_change = 'state' in vals
        result = super().write(vals)
        if notify_status_change:
            self._notify_table_status_changed()
        return result

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

    def action_set_unavailable(self):
        """Set meja menjadi tidak tersedia"""
        active_allocations = self.env['classico.table.allocation'].search([
            ('table_id', 'in', self.ids),
            ('state', '=', 'active'),
            ('reservation_id.state', 'in', ['confirmed', 'arrived']),
        ])
        if active_allocations:
            raise ValidationError('Meja tidak dapat dibuat tidak tersedia karena masih memiliki alokasi aktif')
        self.write({
            'state': 'unavailable',
            'last_updated': fields.Datetime.now(),
            'updated_by': self.env.user.id
        })
        return True

    def _notify_table_status_changed(self):
        """Notify open web clients that table availability changed."""
        self.env['bus.bus']._sendone(
            self._table_bus_channel,
            'classico_table_status_changed',
            {
                'table_ids': self.ids,
                'statistics': self.get_table_statistics(),
            }
        )

    @api.model
    def get_table_statistics(self):
        """Menghitung statistik meja untuk dashboard"""
        total = self.search_count([])
        available = self.search_count([('state', '=', 'available')])
        occupied = self.search_count([('state', '=', 'occupied')])
        reserved = self.search_count([('state', '=', 'reserved')])
        unavailable = self.search_count([('state', '=', 'unavailable')])
        
        return {
            'total': total,
            'available': available,
            'occupied': occupied,
            'reserved': reserved,
            'unavailable': unavailable,
            'availability_rate': (available / total * 100) if total > 0 else 0
        }
