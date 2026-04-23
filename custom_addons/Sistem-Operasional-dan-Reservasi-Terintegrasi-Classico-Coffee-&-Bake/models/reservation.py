# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime


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

    @api.depends('reservation_date', 'reservation_time')
    def _compute_reservation_datetime(self):
        for record in self:
            if record.reservation_date and record.reservation_time:
                hour = int(record.reservation_time)
                minute = int((record.reservation_time % 1) * 60)
                record.reservation_datetime = datetime.combine(
                    record.reservation_date,
                    datetime.min.time().replace(hour=hour, minute=minute)
                )
            else:
                record.reservation_datetime = False

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('classico.reservation') or 'New'
        return super(ClassicoReservation, self).create(vals)

    @api.constrains('guest_count')
    def _check_guest_count(self):
        for record in self:
            if record.guest_count <= 0:
                raise ValidationError('Jumlah tamu harus lebih dari 0')

    @api.constrains('reservation_time')
    def _check_reservation_time(self):
        for record in self:
            if record.reservation_time < 7.0 or record.reservation_time > 22.0:
                raise ValidationError('Waktu reservasi harus antara jam 07:00 - 22:00')

    def action_confirm(self):
        """Konfirmasi reservasi"""
        self.write({'state': 'confirmed'})
        return True

    def action_arrive(self):
        """Tandai pelanggan sudah datang"""
        self.write({'state': 'arrived'})
        return True

    def action_done(self):
        """Selesaikan reservasi"""
        self.write({'state': 'done'})
        if self.table_id:
            self.table_id.write({'state': 'available'})
        return True

    def action_cancel(self):
        """Batalkan reservasi"""
        self.write({'state': 'cancelled'})
        if self.table_id:
            self.table_id.write({'state': 'available'})
        return True

    def action_reset_to_draft(self):
        """Kembalikan ke draft"""
        self.write({'state': 'draft'})
        return True
