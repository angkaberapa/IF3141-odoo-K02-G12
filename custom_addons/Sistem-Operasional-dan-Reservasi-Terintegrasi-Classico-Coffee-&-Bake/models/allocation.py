# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ClassicoTableAllocation(models.Model):
    _name = 'classico.table.allocation'
    _description = 'Alokasi Meja Reservasi'
    _order = 'start_datetime desc, table_id'

    reservation_id = fields.Many2one(
        'classico.reservation',
        string='Reservasi',
        required=True,
        ondelete='cascade'
    )
    table_id = fields.Many2one(
        'classico.table',
        string='Meja',
        required=True,
        ondelete='restrict'
    )
    seats_used = fields.Integer(
        string='Jumlah Kursi Terpakai',
        required=True,
        default=1
    )
    placement_note = fields.Char(string='Catatan Penempatan')
    start_datetime = fields.Datetime(string='Mulai', required=True)
    end_datetime = fields.Datetime(string='Selesai', required=True)
    state = fields.Selection([
        ('active', 'Active'),
        ('released', 'Released'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='active', required=True)

    @api.constrains('seats_used', 'table_id')
    def _check_seats_used(self):
        for record in self:
            if record.seats_used <= 0:
                raise ValidationError('Jumlah kursi terpakai harus lebih dari 0')
            if record.table_id and record.seats_used > record.table_id.capacity:
                raise ValidationError('Jumlah kursi terpakai tidak boleh melebihi kapasitas meja')

    @api.constrains('start_datetime', 'end_datetime')
    def _check_datetime_range(self):
        for record in self:
            if record.start_datetime and record.end_datetime and record.start_datetime >= record.end_datetime:
                raise ValidationError('Waktu selesai alokasi harus setelah waktu mulai')

    @api.constrains('table_id', 'start_datetime', 'end_datetime', 'state')
    def _check_no_overlap(self):
        for record in self.filtered(lambda allocation: allocation.state == 'active'):
            overlapping = self.search_count([
                ('id', '!=', record.id),
                ('table_id', '=', record.table_id.id),
                ('state', '=', 'active'),
                ('start_datetime', '<', record.end_datetime),
                ('end_datetime', '>', record.start_datetime),
                ('reservation_id.state', 'in', ['confirmed', 'arrived']),
            ])
            if overlapping:
                raise ValidationError('Meja sudah dialokasikan pada rentang waktu tersebut')
