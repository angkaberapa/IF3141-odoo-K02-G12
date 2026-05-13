# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta


class ClassicoEvaluationReport(models.Model):
    _name = 'classico.evaluation.report'
    _description = 'Laporan Evaluasi Operasional'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, date_end desc'

    name = fields.Char(string='Nomor Laporan Evaluasi', required=True, copy=False, readonly=True, default='New')
    date_start = fields.Date(string='Tanggal Mulai', required=True, tracking=True)
    date_end = fields.Date(string='Tanggal Akhir', required=True, tracking=True)
    total_reservations = fields.Integer(string='Total Reservasi', readonly=True)
    total_complaints = fields.Integer(string='Total Keluhan', readonly=True)
    total_shift_reports = fields.Integer(string='Total Laporan Shift', readonly=True)
    total_operational_notes = fields.Integer(string='Total Catatan Operasional', readonly=True)
    reservation_summary = fields.Text(string='Ringkasan Reservasi', readonly=True)
    complaint_summary = fields.Text(string='Ringkasan Keluhan', readonly=True)
    shift_summary = fields.Text(string='Ringkasan Shift', readonly=True)
    content_report = fields.Text(string='Konten Laporan', readonly=True)
    generated_by = fields.Many2one('res.users', string='Dibuat Oleh', readonly=True)
    generated_at = fields.Datetime(string='Waktu Generate', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('generated', 'Generated'),
    ], string='Status', default='draft', required=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('classico.evaluation.report') or 'New'
        return super().create(vals_list)

    @api.constrains('date_start', 'date_end')
    def _check_date_range(self):
        for record in self:
            if record.date_start and record.date_end and record.date_start > record.date_end:
                raise ValidationError('Tanggal mulai tidak boleh setelah tanggal akhir')

    def action_generate(self):
        for record in self:
            if record.date_start > record.date_end:
                raise ValidationError('Rentang tanggal tidak valid')

            reservations = self.env['classico.reservation'].search([
                ('reservation_date', '>=', record.date_start),
                ('reservation_date', '<=', record.date_end),
            ])
            complaints = self.env['classico.complaint'].search([
                ('incident_datetime', '>=', fields.Datetime.to_datetime(record.date_start)),
                ('incident_datetime', '<', fields.Datetime.to_datetime(record.date_end) + timedelta(days=1)),
            ])
            shift_reports = self.env['classico.shift.report'].search([
                ('report_date', '>=', record.date_start),
                ('report_date', '<=', record.date_end),
            ])
            notes = self.env['classico.operational.note'].search([
                ('note_date', '>=', record.date_start),
                ('note_date', '<=', record.date_end),
            ])

            reservation_summary = 'Reservasi berdasarkan status: ' + ', '.join(
                '%s=%s' % (state, len(reservations.filtered(lambda r, state=state: r.state == state)))
                for state in ['draft', 'confirmed', 'arrived', 'done', 'cancelled']
            )
            complaint_summary = 'Keluhan berdasarkan status: ' + ', '.join(
                '%s=%s' % (state, len(complaints.filtered(lambda c, state=state: c.state == state)))
                for state in ['open', 'in_progress', 'resolved', 'closed']
            )
            shift_summary = 'Laporan shift berdasarkan divisi: ' + ', '.join(
                '%s=%s' % (division, len(shift_reports.filtered(lambda s, division=division: s.division == division)))
                for division in ['floor', 'kitchen', 'bar', 'bakery', 'stock_keeper', 'cashier']
            )

            record.write({
                'total_reservations': len(reservations),
                'total_complaints': len(complaints),
                'total_shift_reports': len(shift_reports),
                'total_operational_notes': len(notes),
                'reservation_summary': reservation_summary,
                'complaint_summary': complaint_summary,
                'shift_summary': shift_summary,
                'content_report': '\n'.join([reservation_summary, complaint_summary, shift_summary]),
                'generated_by': self.env.user.id,
                'generated_at': fields.Datetime.now(),
                'state': 'generated',
            })
        return True
