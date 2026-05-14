# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta


UPCOMING_RESERVATION_WARNING_HOURS = 5


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
    ], string='Status Fisik Saat Ini', default='available', required=True, tracking=True,
       help='Status ini adalah kondisi real-time di lantai restoran. Reservasi masa depan dilihat dari jadwal alokasi, bukan dari status fisik ini.')

    floor_section = fields.Selection([
        ('indoor', 'Indoor'),
        ('outdoor', 'Outdoor'),
        ('vip', 'VIP Area')
    ], string='Area', default='indoor', tracking=True)

    current_reservation_id = fields.Many2one(
        'classico.reservation',
        string='Reservasi Aktif Saat Ini',
        compute='_compute_reservation_summary',
        store=False
    )

    active_allocation_id = fields.Many2one(
        'classico.table.allocation',
        string='Alokasi Aktif Saat Ini',
        compute='_compute_reservation_summary',
        store=False
    )

    next_allocation_id = fields.Many2one(
        'classico.table.allocation',
        string='Reservasi Berikutnya',
        compute='_compute_reservation_summary',
        store=False
    )

    next_reservation_id = fields.Many2one(
        'classico.reservation',
        string='Detail Reservasi Berikutnya',
        compute='_compute_reservation_summary',
        store=False
    )

    current_customer_info = fields.Char(
        string='Pelanggan Saat Ini',
        compute='_compute_reservation_summary',
        store=False
    )

    next_reservation_info = fields.Char(
        string='Reservasi Berikutnya',
        compute='_compute_reservation_summary',
        store=False
    )

    allocation_ids = fields.One2many(
        'classico.table.allocation',
        'table_id',
        string='Riwayat/Jadwal Reservasi'
    )

    active_reservation_count = fields.Integer(
        string='Jumlah Jadwal Aktif',
        compute='_compute_active_reservation_count'
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

    def _compute_reservation_summary(self):
        now = fields.Datetime.now()
        for record in self:
            active_allocation = self.env['classico.table.allocation'].search([
                ('table_id', '=', record.id),
                ('state', '=', 'active'),
                ('start_datetime', '<=', now),
                ('end_datetime', '>=', now),
                ('reservation_id.state', 'in', ['confirmed', 'arrived']),
            ], order='start_datetime asc', limit=1)

            next_allocation = self.env['classico.table.allocation'].search([
                ('table_id', '=', record.id),
                ('state', '=', 'active'),
                ('start_datetime', '>', now),
                ('reservation_id.state', 'in', ['draft', 'confirmed']),
            ], order='start_datetime asc', limit=1)

            record.active_allocation_id = active_allocation
            record.current_reservation_id = active_allocation.reservation_id
            record.next_allocation_id = next_allocation
            record.next_reservation_id = next_allocation.reservation_id

            if active_allocation:
                reservation = active_allocation.reservation_id
                record.current_customer_info = '%s (%s tamu, sampai %s)' % (
                    reservation.customer_name,
                    reservation.guest_count,
                    fields.Datetime.context_timestamp(record, active_allocation.end_datetime).strftime('%H:%M')
                )
            else:
                record.current_customer_info = 'Tidak ada reservasi aktif saat ini'

            if next_allocation:
                reservation = next_allocation.reservation_id
                record.next_reservation_info = '%s - %s (%s tamu)' % (
                    fields.Datetime.context_timestamp(record, next_allocation.start_datetime).strftime('%d/%m %H:%M'),
                    reservation.customer_name,
                    reservation.guest_count
                )
            else:
                record.next_reservation_info = 'Tidak ada reservasi berikutnya'

    def _compute_active_reservation_count(self):
        for record in self:
            record.active_reservation_count = self.env['classico.table.allocation'].search_count([
                ('table_id', '=', record.id),
                ('state', '=', 'active'),
                ('reservation_id.state', 'in', ['draft', 'confirmed', 'arrived']),
            ])

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

    def _get_upcoming_allocations_within_warning_window(self):
        now = fields.Datetime.now()
        warning_limit = now + timedelta(hours=UPCOMING_RESERVATION_WARNING_HOURS)
        return self.env['classico.table.allocation'].search([
            ('table_id', 'in', self.ids),
            ('state', '=', 'active'),
            ('start_datetime', '>=', now),
            ('start_datetime', '<=', warning_limit),
            ('reservation_id.state', 'in', ['draft', 'confirmed']),
        ], order='start_datetime asc')

    def _format_upcoming_warning(self, allocations):
        lines = []
        for allocation in allocations:
            reservation = allocation.reservation_id
            start_local = fields.Datetime.context_timestamp(self, allocation.start_datetime).strftime('%d/%m %H:%M')
            end_local = fields.Datetime.context_timestamp(self, allocation.end_datetime).strftime('%H:%M')
            table_name = allocation.table_id.name if allocation.table_id.name.lower().startswith('meja') else 'Meja %s' % allocation.table_id.name
            lines.append('%s-%s: %s sudah dibooking oleh %s (%s tamu, kontak: %s)' % (
                start_local,
                end_local,
                table_name,
                reservation.customer_name,
                reservation.guest_count,
                reservation.customer_phone or '-',
            ))
        return '\n'.join(lines)

    def action_set_available(self):
        """Set meja menjadi tersedia."""
        self.write({
            'state': 'available',
            'last_updated': fields.Datetime.now(),
            'updated_by': self.env.user.id
        })
        return True

    def action_set_occupied(self):
        """Set meja menjadi terisi.

        Jika meja memiliki reservasi dalam 5 jam ke depan, sistem tetap mengizinkan
        perubahan status karena ini merepresentasikan kondisi fisik saat ini, tetapi
        memberikan warning agar waiter dapat mencarikan meja lain untuk walk-in.
        """
        upcoming_allocations = self._get_upcoming_allocations_within_warning_window()
        self.write({
            'state': 'occupied',
            'last_updated': fields.Datetime.now(),
            'updated_by': self.env.user.id
        })
        if upcoming_allocations:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Warning: Ada reservasi mendatang',
                    'message': 'Meja tetap ditandai terisi. Perhatikan reservasi dalam 5 jam ke depan:\n%s' % self._format_upcoming_warning(upcoming_allocations),
                    'sticky': True,
                    'type': 'warning',
                }
            }
        return True

    def action_set_reserved(self):
        """Set meja menjadi dipesan secara manual bila staf membutuhkan status fisik ini."""
        self.write({
            'state': 'reserved',
            'last_updated': fields.Datetime.now(),
            'updated_by': self.env.user.id
        })
        return True

    def action_set_unavailable(self):
        """Set meja menjadi tidak tersedia."""
        active_allocations = self.env['classico.table.allocation'].search([
            ('table_id', 'in', self.ids),
            ('state', '=', 'active'),
            ('reservation_id.state', 'in', ['confirmed', 'arrived']),
        ])
        if active_allocations:
            raise ValidationError('Meja tidak dapat dibuat tidak tersedia karena masih memiliki alokasi reservasi aktif')
        self.write({
            'state': 'unavailable',
            'last_updated': fields.Datetime.now(),
            'updated_by': self.env.user.id
        })
        return True

    def action_view_allocations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Jadwal Reservasi Meja %s' % self.name,
            'res_model': 'classico.table.allocation',
            'view_mode': 'tree,form,calendar',
            'domain': [('table_id', '=', self.id)],
            'context': {'search_default_active_schedule': 1},
        }

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
        """Menghitung statistik meja untuk dashboard status fisik saat ini."""
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
