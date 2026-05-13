# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ClassicoOperationalNote(models.Model):
    _name = 'classico.operational.note'
    _description = 'Catatan Operasional'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'note_date desc, urgency desc'

    name = fields.Char(string='Nomor Catatan', required=True, copy=False, readonly=True, default='New')
    note_date = fields.Date(string='Tanggal', required=True, default=fields.Date.context_today, tracking=True)
    division = fields.Selection([
        ('floor', 'Floor Leader (Waiter/Waitress)'),
        ('kitchen', 'Kitchen'),
        ('bar', 'Barista'),
        ('bakery', 'Bakery'),
        ('stock_keeper', 'Stock Keeper'),
        ('cashier', 'Cashier'),
        ('management', 'Management'),
    ], string='Divisi', tracking=True)
    urgency = fields.Selection([
        ('normal', 'Normal'),
        ('important', 'Important'),
        ('urgent', 'Urgent'),
    ], string='Urgensi', default='normal', required=True, tracking=True)
    description = fields.Text(string='Deskripsi', required=True, tracking=True)
    shift_report_id = fields.Many2one('classico.shift.report', string='Laporan Shift')
    created_by = fields.Many2one('res.users', string='Dibuat Oleh', default=lambda self: self.env.user, readonly=True)
    state = fields.Selection([
        ('open', 'Open'),
        ('archived', 'Archived'),
    ], string='Status', default='open', required=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            shift_report_id = vals.get('shift_report_id')
            if shift_report_id:
                shift_report = self.env['classico.shift.report'].browse(shift_report_id)
                if shift_report.state == 'reviewed':
                    raise ValidationError('Catatan tidak bisa ditambahkan karena laporan sudah direview.')
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('classico.operational.note') or 'New'
        return super().create(vals_list)

    @api.constrains('note_date')
    def _check_note_date(self):
        for record in self:
            if record.note_date > fields.Date.today():
                raise ValidationError('Tanggal catatan tidak boleh di masa depan')

    def action_archive(self):
        self.write({'state': 'archived'})
        return True

    def action_reopen(self):
        self.write({'state': 'open'})
        return True

    def write(self, vals):
        for record in self:
            if record.shift_report_id and record.shift_report_id.state == 'reviewed':
                raise ValidationError('Catatan tidak bisa diubah karena laporan sudah direview.')
        return super().write(vals)

    def unlink(self):
        for record in self:
            if record.shift_report_id and record.shift_report_id.state == 'reviewed':
                raise ValidationError('Catatan tidak bisa dihapus karena laporan sudah direview.')
        return super().unlink()
