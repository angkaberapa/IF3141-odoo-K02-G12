# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ClassicoShift(models.Model):
    _name = 'classico.shift'
    _description = 'Shift Operasional'
    _order = 'start_time, name'

    name = fields.Char(string='Nama Shift', required=True)
    start_time = fields.Float(string='Waktu Mulai', required=True, help='Format: 7.5 untuk 07:30')
    end_time = fields.Float(string='Waktu Selesai', required=True, help='Format: 15.0 untuk 15:00')
    description = fields.Text(string='Deskripsi')
    active = fields.Boolean(string='Aktif', default=True)

    _sql_constraints = [
        ('unique_shift_name', 'UNIQUE(name)', 'Nama shift sudah digunakan!')
    ]

    @api.constrains('start_time', 'end_time')
    def _check_shift_time(self):
        for record in self:
            if record.start_time < 0 or record.start_time >= 24:
                raise ValidationError('Waktu mulai shift harus berada pada rentang 00:00 - 23:59')
            if record.end_time <= 0 or record.end_time > 24:
                raise ValidationError('Waktu selesai shift harus berada pada rentang 00:01 - 24:00')
            if record.start_time == record.end_time:
                raise ValidationError('Waktu mulai dan selesai shift tidak boleh sama')


class ClassicoShiftReport(models.Model):
    _name = 'classico.shift.report'
    _description = 'Laporan Shift Digital'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'report_date desc, shift_type desc'

    # FR-03: Sistem dapat mencatat laporan shift digital
    name = fields.Char(
        string='Nomor Laporan',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        tracking=True
    )
    
    report_date = fields.Date(
        string='Tanggal Laporan',
        required=True,
        default=fields.Date.context_today,
        tracking=True
    )
    
    shift_type = fields.Selection([
        ('morning', 'Pagi (07:00 - 15:00)'),
        ('evening', 'Malam (15:00 - 23:00)')
    ], string='Shift', required=True, tracking=True)

    shift_id = fields.Many2one(
        'classico.shift',
        string='Data Shift',
        tracking=True,
        help='Referensi master shift operasional'
    )
    
    division = fields.Selection([
        ('floor', 'Floor Service'),
        ('kitchen', 'Kitchen'),
        ('bar', 'Bar'),
        ('bakery', 'Bakery')
    ], string='Divisi', required=True, tracking=True)
    
    operational_condition = fields.Text(
        string='Kondisi Operasional',
        required=True,
        tracking=True,
        help='Rangkuman kondisi operasional selama shift'
    )
    
    technical_issues = fields.Text(
        string='Kendala Teknis',
        tracking=True,
        help='Masalah teknis yang terjadi selama shift'
    )
    
    special_instructions = fields.Text(
        string='Instruksi Khusus untuk Shift Berikutnya',
        tracking=True
    )
    
    unfinished_tasks = fields.Text(
        string='Tugas yang Belum Selesai',
        tracking=True
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('reviewed', 'Reviewed')
    ], string='Status', default='draft', required=True, tracking=True)
    
    submitted_by = fields.Many2one(
        'res.users',
        string='Disubmit Oleh',
        readonly=True
    )
    
    submit_datetime = fields.Datetime(
        string='Waktu Submit',
        readonly=True
    )
    
    reviewed_by = fields.Many2one(
        'res.users',
        string='Direview Oleh',
        readonly=True
    )
    
    review_datetime = fields.Datetime(
        string='Waktu Review',
        readonly=True
    )
    
    # OW-04: Template berbeda per divisi
    floor_specific_notes = fields.Text(
        string='Catatan Khusus Floor',
        help='Status meja, keluhan pelanggan, dll'
    )
    
    kitchen_specific_notes = fields.Text(
        string='Catatan Khusus Kitchen',
        help='Stok bahan, menu unavailable, dll'
    )
    
    bar_specific_notes = fields.Text(
        string='Catatan Khusus Bar',
        help='Stok minuman, peralatan bar, dll'
    )
    
    bakery_specific_notes = fields.Text(
        string='Catatan Khusus Bakery',
        help='Produk pre-order, stok bahan baku, dll'
    )

    operational_note_ids = fields.One2many(
        'classico.operational.note',
        'shift_report_id',
        string='Catatan Operasional'
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('classico.shift.report') or 'New'
        return super().create(vals_list)

    def action_submit(self):
        """Submit laporan shift"""
        self.write({
            'state': 'submitted',
            'submitted_by': self.env.user.id,
            'submit_datetime': fields.Datetime.now()
        })
        # OW-04: Laporan shift wajib didokumentasikan sebelum meninggalkan area
        return True

    def action_review(self):
        """Review laporan oleh manager"""
        self.write({
            'state': 'reviewed',
            'reviewed_by': self.env.user.id,
            'review_datetime': fields.Datetime.now()
        })
        return True

    def action_reset_to_draft(self):
        """Kembalikan ke draft"""
        self.write({'state': 'draft'})
        return True

    @api.constrains('report_date')
    def _check_report_date(self):
        for record in self:
            if record.report_date > fields.Date.today():
                raise ValidationError('Tanggal laporan tidak boleh di masa depan')
