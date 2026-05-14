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
    
    # Advanced Metrics
    average_resolution_time = fields.Float(string='Rata-rata Waktu Penyelesaian Keluhan (jam)', readonly=True, digits=(10, 2))
    complaint_rate = fields.Float(string='Tingkat Keluhan (per 100 reservasi)', readonly=True, digits=(10, 2))
    top_complaint_category = fields.Char(string='Kategori Keluhan Terbanyak', readonly=True)
    most_active_division = fields.Char(string='Divisi Paling Aktif', readonly=True)
    peak_reservation_day = fields.Char(string='Hari Tersibuk Reservasi', readonly=True)
    
    reservation_summary = fields.Text(string='Ringkasan Reservasi', readonly=True)
    complaint_summary = fields.Text(string='Ringkasan Keluhan', readonly=True)
    shift_summary = fields.Text(string='Ringkasan Shift', readonly=True)
    pdf_url = fields.Char(string='PDF URL', compute='_compute_pdf_url', readonly=True)
    pdf_viewer = fields.Html(string='PDF Viewer', compute='_compute_pdf_viewer', readonly=True, sanitize=False)
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

    @api.depends('state')
    def _compute_pdf_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            if record.id and record.state == 'generated':
                record.pdf_url = f"{base_url}/report/pdf/Sistem-Operasional-dan-Reservasi-Terintegrasi-Classico-Coffee-&-Bake.report_evaluation_document/{record.id}"
            else:
                record.pdf_url = False

    @api.depends('pdf_url')
    def _compute_pdf_viewer(self):
        for record in self:
            if record.pdf_url:
                record.pdf_viewer = f'''
                    <div style="width: 100%; height: 800px; border: 1px solid #ddd; border-radius: 5px; overflow: hidden;">
                        <iframe src="{record.pdf_url}" 
                                style="width: 100%; height: 100%; border: none;" 
                                frameborder="0">
                        </iframe>
                    </div>
                '''
            else:
                record.pdf_viewer = False

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

            res_states = {
                'draft': ('Draft', len(reservations.filtered(lambda r: r.state == 'draft'))),
                'confirmed': ('Confirmed', len(reservations.filtered(lambda r: r.state == 'confirmed'))),
                'arrived': ('Arrived', len(reservations.filtered(lambda r: r.state == 'arrived'))),
                'done': ('Done', len(reservations.filtered(lambda r: r.state == 'done'))),
                'cancelled': ('Cancelled', len(reservations.filtered(lambda r: r.state == 'cancelled'))),
            }
            
            comp_states = {
                'open': ('Open', len(complaints.filtered(lambda c: c.state == 'open'))),
                'in_progress': ('In Progress', len(complaints.filtered(lambda c: c.state == 'in_progress'))),
                'resolved': ('Resolved', len(complaints.filtered(lambda c: c.state == 'resolved'))),
                'closed': ('Closed', len(complaints.filtered(lambda c: c.state == 'closed'))),
            }
            
            shift_divs = {
                'floor': ('Floor', len(shift_reports.filtered(lambda s: s.division == 'floor'))),
                'kitchen': ('Kitchen', len(shift_reports.filtered(lambda s: s.division == 'kitchen'))),
                'bar': ('Bar', len(shift_reports.filtered(lambda s: s.division == 'bar'))),
                'bakery': ('Bakery', len(shift_reports.filtered(lambda s: s.division == 'bakery'))),
                'stock_keeper': ('Stock Keeper', len(shift_reports.filtered(lambda s: s.division == 'stock_keeper'))),
                'cashier': ('Cashier', len(shift_reports.filtered(lambda s: s.division == 'cashier'))),
            }

            reservation_summary = 'Reservasi berdasarkan status:\n' + '\n'.join(
                '  • %s: %d reservasi' % (label, count) 
                for state, (label, count) in res_states.items()
            )
            
            complaint_summary = 'Keluhan berdasarkan status:\n' + '\n'.join(
                '  • %s: %d keluhan' % (label, count)
                for state, (label, count) in comp_states.items()
            )
            
            shift_summary = 'Laporan shift berdasarkan divisi:\n' + '\n'.join(
                '  • %s: %d laporan' % (label, count)
                for division, (label, count) in shift_divs.items()
            )
            
            resolved_complaints = complaints.filtered(lambda c: c.resolution_time and c.resolution_time > 0)
            avg_resolution = sum(resolved_complaints.mapped('resolution_time')) / len(resolved_complaints) if resolved_complaints else 0.0
            
            complaint_rate = (len(complaints) / len(reservations) * 100) if reservations else 0.0
            
            category_counts = {}
            for comp in complaints:
                category_counts[comp.category] = category_counts.get(comp.category, 0) + 1
            top_category = max(category_counts.items(), key=lambda x: x[1])[0] if category_counts else 'N/A'
            category_labels = dict(complaints._fields['category'].selection)
            top_category_label = category_labels.get(top_category, top_category)
            
            division_counts = {}
            for shift in shift_reports:
                division_counts[shift.division] = division_counts.get(shift.division, 0) + 1
            most_active = max(division_counts.items(), key=lambda x: x[1])[0] if division_counts else 'N/A'
            division_labels = dict(shift_reports._fields['division'].selection)
            most_active_label = division_labels.get(most_active, most_active)
            
            day_counts = {}
            for res in reservations:
                day_name = res.reservation_date.strftime('%A')  # Monday, Tuesday, etc.
                day_counts[day_name] = day_counts.get(day_name, 0) + 1
            peak_day = max(day_counts.items(), key=lambda x: x[1])[0] if day_counts else 'N/A'

            record.write({
                'total_reservations': len(reservations),
                'total_complaints': len(complaints),
                'total_shift_reports': len(shift_reports),
                'total_operational_notes': len(notes),
                'average_resolution_time': avg_resolution,
                'complaint_rate': complaint_rate,
                'top_complaint_category': top_category_label,
                'most_active_division': most_active_label,
                'peak_reservation_day': peak_day,
                'reservation_summary': reservation_summary,
                'complaint_summary': complaint_summary,
                'shift_summary': shift_summary,
                'generated_by': self.env.user.id,
                'generated_at': fields.Datetime.now(),
                'state': 'generated',
            })
        return True

    def dummy_action(self):
        """do nothing, just for display"""
        return True
