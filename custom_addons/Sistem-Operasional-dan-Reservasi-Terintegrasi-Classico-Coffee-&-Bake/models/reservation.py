# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class ClassicoReservation(models.Model):
    _name = 'classico.reservation'
    _description = 'Manajemen Reservasi Pelanggan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'reservation_date desc, reservation_time desc'

    # FR-01: Sistem mampu mengelola permintaan reservasi pelanggan
    name = fields.Char(
        string='Nomor Reservasi',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        tracking=True
    )
    
    customer_name = fields.Char(
        string='Nama Pelanggan',
        required=True,
        tracking=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Pelanggan',
        tracking=True,
        help='Data pelanggan Odoo yang terhubung dengan reservasi ini'
    )
    
    customer_phone = fields.Char(
        string='Nomor Kontak',
        required=True,
        tracking=True
    )
    
    reservation_date = fields.Date(
        string='Tanggal Reservasi',
        required=True,
        default=fields.Date.context_today,
        tracking=True
    )
    
    reservation_time = fields.Float(
        string='Waktu Reservasi',
        required=True,
        tracking=True,
        help='Format: 14.5 untuk 14:30'
    )

    duration_hours = fields.Float(
        string='Durasi Reservasi (jam)',
        required=True,
        default=2.0,
        tracking=True
    )
    
    guest_count = fields.Integer(
        string='Jumlah Tamu',
        required=True,
        default=1,
        tracking=True
    )
    
    special_request = fields.Text(
        string='Permintaan Khusus',
        tracking=True
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('arrived', 'Arrived'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)
    
    table_id = fields.Many2one(
        'classico.table',
        string='Meja',
        tracking=True
    )

    allocation_ids = fields.One2many(
        'classico.table.allocation',
        'reservation_id',
        string='Alokasi Meja'
    )

    table_ids = fields.Many2many(
        'classico.table',
        string='Meja Dialokasikan',
        compute='_compute_table_ids'
    )
    
    created_by = fields.Many2one(
        'res.users',
        string='Dibuat Oleh',
        default=lambda self: self.env.user,
        readonly=True
    )
    
    reservation_datetime = fields.Datetime(
        string='Waktu Reservasi Lengkap',
        compute='_compute_reservation_datetime',
        store=True
    )

    reservation_end_datetime = fields.Datetime(
        string='Waktu Selesai Reservasi',
        compute='_compute_reservation_end_datetime',
        store=True
    )

    allocated_capacity = fields.Integer(
        string='Kapasitas Dialokasikan',
        compute='_compute_allocated_capacity'
    )

    availability_message = fields.Char(
        string='Status Ketersediaan',
        compute='_compute_availability_message'
    )

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for record in self:
            if record.partner_id:
                record.customer_name = record.partner_id.name
                record.customer_phone = record.partner_id.phone or record.partner_id.mobile

    @api.depends('reservation_date', 'reservation_time')
    def _compute_reservation_datetime(self):
        for record in self:
            if record.reservation_date and record.reservation_time:
                hour = int(record.reservation_time)
                minute = int(round((record.reservation_time % 1) * 60))
                record.reservation_datetime = datetime.combine(
                    record.reservation_date,
                    datetime.min.time().replace(hour=hour, minute=minute)
                )
            else:
                record.reservation_datetime = False

    @api.depends('reservation_datetime', 'duration_hours')
    def _compute_reservation_end_datetime(self):
        for record in self:
            if record.reservation_datetime and record.duration_hours:
                record.reservation_end_datetime = record.reservation_datetime + timedelta(hours=record.duration_hours)
            else:
                record.reservation_end_datetime = False

    @api.depends('allocation_ids.table_id', 'allocation_ids.state')
    def _compute_table_ids(self):
        for record in self:
            record.table_ids = record.allocation_ids.filtered(
                lambda allocation: allocation.state == 'active'
            ).mapped('table_id')

    @api.depends('allocation_ids.table_id.capacity', 'allocation_ids.state')
    def _compute_allocated_capacity(self):
        for record in self:
            record.allocated_capacity = sum(record.allocation_ids.filtered(
                lambda allocation: allocation.state == 'active'
            ).mapped('table_id.capacity'))

    @api.depends('reservation_datetime', 'reservation_end_datetime', 'guest_count', 'allocation_ids')
    def _compute_availability_message(self):
        for record in self:
            if not record.reservation_datetime or not record.reservation_end_datetime:
                record.availability_message = 'Tanggal dan waktu reservasi belum lengkap'
            else:
                tables = record._get_available_tables()
                capacity = sum(tables.mapped('capacity'))
                record.availability_message = 'Meja tersedia' if capacity >= record.guest_count else 'Kapasitas meja tidak mencukupi'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('classico.reservation') or 'New'
        return super().create(vals_list)

    @api.constrains('guest_count')
    def _check_guest_count(self):
        for record in self:
            if record.guest_count <= 0:
                raise ValidationError('Jumlah tamu harus lebih dari 0')

    @api.constrains('duration_hours')
    def _check_duration_hours(self):
        for record in self:
            if record.duration_hours <= 0:
                raise ValidationError('Durasi reservasi harus lebih dari 0 jam')

    @api.constrains('reservation_time')
    def _check_reservation_time(self):
        for record in self:
            if record.reservation_time < 7.0 or record.reservation_time > 22.0:
                raise ValidationError('Waktu reservasi harus antara jam 07:00 - 22:00')

    def _get_overlapping_allocations(self, table):
        self.ensure_one()
        if not self.reservation_datetime or not self.reservation_end_datetime:
            return self.env['classico.table.allocation']

        return self.env['classico.table.allocation'].search([
            ('table_id', '=', table.id),
            ('reservation_id', '!=', self.id or 0),
            ('state', '=', 'active'),
            ('start_datetime', '<', self.reservation_end_datetime),
            ('end_datetime', '>', self.reservation_datetime),
            ('reservation_id.state', 'in', ['confirmed', 'arrived']),
        ])

    def _get_available_tables(self):
        self.ensure_one()
        tables = self.env['classico.table'].search([('state', '!=', 'unavailable')], order='capacity asc, name asc')
        return tables.filtered(lambda table: not self._get_overlapping_allocations(table))

    def _select_tables_for_capacity(self):
        self.ensure_one()
        available_tables = self._get_available_tables()
        selected = self.env['classico.table']
        total_capacity = 0

        if self.table_id:
            if self.table_id.state == 'unavailable':
                raise ValidationError('Meja pilihan sedang tidak tersedia')
            if self.table_id.capacity < self.guest_count:
                raise ValidationError('Kapasitas meja pilihan tidak mencukupi jumlah tamu')
            if self._get_overlapping_allocations(self.table_id):
                raise ValidationError('Meja pilihan sudah dialokasikan pada waktu tersebut')
            selected |= self.table_id
            total_capacity += self.table_id.capacity

        for table in available_tables - selected:
            if total_capacity >= self.guest_count:
                break
            selected |= table
            total_capacity += table.capacity

        if total_capacity < self.guest_count:
            raise ValidationError('Tidak ada kapasitas meja yang mencukupi untuk reservasi ini')

        return selected

    def action_allocate_tables(self):
        for record in self:
            record.allocation_ids.filtered(lambda allocation: allocation.state == 'active').write({'state': 'cancelled'})
            selected_tables = record._select_tables_for_capacity()
            remaining_guests = record.guest_count
            for table in selected_tables:
                seats_used = min(table.capacity, remaining_guests)
                remaining_guests -= seats_used
                self.env['classico.table.allocation'].create({
                    'reservation_id': record.id,
                    'table_id': table.id,
                    'seats_used': seats_used,
                    'start_datetime': record.reservation_datetime,
                    'end_datetime': record.reservation_end_datetime,
                })
            selected_tables.write({'state': 'reserved'})
            record.table_id = selected_tables[:1].id if selected_tables else False
        return True

    def action_confirm(self):
        """Konfirmasi reservasi"""
        for record in self:
            if not record.allocation_ids.filtered(lambda allocation: allocation.state == 'active'):
                record.action_allocate_tables()
            if record.allocated_capacity < record.guest_count:
                raise ValidationError('Kapasitas alokasi meja belum mencukupi jumlah tamu')
            record.write({'state': 'confirmed'})
        return True

    def action_arrive(self):
        """Tandai pelanggan sudah datang"""
        self.write({'state': 'arrived'})
        self.mapped('table_ids').write({'state': 'occupied'})
        return True

    def action_done(self):
        """Selesaikan reservasi"""
        tables = self.mapped('table_ids')
        self.write({'state': 'done'})
        self.mapped('allocation_ids').filtered(lambda allocation: allocation.state == 'active').write({'state': 'released'})
        tables.write({'state': 'available'})
        return True

    def action_cancel(self):
        """Batalkan reservasi"""
        tables = self.mapped('table_ids')
        self.write({'state': 'cancelled'})
        self.mapped('allocation_ids').filtered(lambda allocation: allocation.state == 'active').write({'state': 'cancelled'})
        tables.write({'state': 'available'})
        return True

    def action_reset_to_draft(self):
        """Kembalikan ke draft"""
        self.write({'state': 'draft'})
        return True
