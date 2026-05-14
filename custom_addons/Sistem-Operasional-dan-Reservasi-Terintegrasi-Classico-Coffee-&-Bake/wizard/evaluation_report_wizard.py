# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta


class EvaluationReportWizard(models.TransientModel):
    _name = 'classico.evaluation.report.wizard'
    _description = 'Wizard Generate Laporan Evaluasi'

    date_start = fields.Date(
        string='Tanggal Mulai',
        required=True,
        default=lambda self: fields.Date.today() - timedelta(days=7)
    )
    date_end = fields.Date(
        string='Tanggal Akhir',
        required=True,
        default=fields.Date.today
    )
    report_period = fields.Selection([
        ('week', 'Minggu Ini'),
        ('month', 'Bulan Ini'),
        ('quarter', 'Quarter Ini (3 Bulan)'),
        ('custom', 'Custom Range'),
    ], string='Periode', default='week', required=True)

    @api.onchange('report_period')
    def _onchange_report_period(self):
        """Auto-fill date range based on selected period"""
        today = fields.Date.today()
        
        if self.report_period == 'week':
            # Last 7 days
            self.date_start = today - timedelta(days=7)
            self.date_end = today
        elif self.report_period == 'month':
            # This month
            self.date_start = today.replace(day=1)
            self.date_end = today
        elif self.report_period == 'quarter':
            # Last 90 days
            self.date_start = today - timedelta(days=90)
            self.date_end = today
        # For 'custom', user manually selects dates

    @api.constrains('date_start', 'date_end')
    def _check_date_range(self):
        """Validate date range"""
        for record in self:
            if record.date_start > record.date_end:
                raise ValidationError('Tanggal mulai tidak boleh setelah tanggal akhir!')
            
            # Check if date range is too large (> 1 year)
            date_diff = (record.date_end - record.date_start).days
            if date_diff > 365:
                raise ValidationError('Rentang tanggal terlalu panjang! Maksimal 1 tahun (365 hari).')
    
    def action_generate_report(self):
        """Generate evaluation report with selected date range"""
        self.ensure_one()
        
        # Validate again
        if self.date_start > self.date_end:
            raise ValidationError('Tanggal mulai tidak boleh setelah tanggal akhir!')
        
        # Create evaluation report record
        report = self.env['classico.evaluation.report'].create({
            'date_start': self.date_start,
            'date_end': self.date_end,
        })
        
        # Trigger auto-generation
        report.action_generate()
        
        # Open the generated report in form view
        return {
            'type': 'ir.actions.act_window',
            'name': 'Laporan Evaluasi',
            'res_model': 'classico.evaluation.report',
            'res_id': report.id,
            'view_mode': 'form',
            'view_id': self.env.ref('Sistem-Operasional-dan-Reservasi-Terintegrasi-Classico-Coffee-&-Bake.view_classico_evaluation_report_form').id,
            'target': 'current',
        }
