# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ClassicoComplaint(models.Model):
    _name = 'classico.complaint'
    _description = 'Ticketing Keluhan Pelanggan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # FR-04: Sistem mampu mengelola keluhan dari pelanggan
    name = fields.Char(
        string='Nomor Tiket',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        tracking=True
    )
    
    complaint_description = fields.Text(
        string='Deskripsi Keluhan',
        required=True,
        tracking=True
    )
    
    incident_datetime = fields.Datetime(
        string='Waktu Kejadian',
        required=True,
        default=fields.Datetime.now,
        tracking=True
    )
    
    customer_name = fields.Char(
        string='Nama Pelanggan (Opsional)',
        tracking=True
    )
    
    category = fields.Selection([
        ('food', 'Makanan'),
        ('beverage', 'Minuman'),
        ('service', 'Pelayanan'),
        ('cleanliness', 'Kebersihan'),
        ('facility', 'Fasilitas'),
        ('other', 'Lainnya')
    ], string='Kategori', required=True, tracking=True)
    
    priority = fields.Selection([
        ('low', 'Rendah'),
        ('medium', 'Sedang'),
        ('high', 'Tinggi'),
        ('urgent', 'Mendesak')
    ], string='Prioritas', default='medium', required=True, tracking=True)
    
    state = fields.Selection([
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed')
    ], string='Status', default='open', required=True, tracking=True)
    
    responsible_division = fields.Selection([
        ('floor', 'Floor Service'),
        ('kitchen', 'Kitchen'),
        ('bar', 'Bar'),
        ('bakery', 'Bakery'),
        ('management', 'Management')
    ], string='Divisi Penanggung Jawab', tracking=True)
    
    assigned_to = fields.Many2one(
        'res.users',
        string='Ditugaskan Kepada',
        tracking=True
    )
    
    resolution_notes = fields.Text(
        string='Catatan Penyelesaian',
        tracking=True
    )
    
    reported_by = fields.Many2one(
        'res.users',
        string='Dilaporkan Oleh',
        default=lambda self: self.env.user,
        readonly=True,
        tracking=True
    )
    
    resolution_datetime = fields.Datetime(
        string='Waktu Penyelesaian',
        readonly=True
    )
    
    resolution_time = fields.Float(
        string='Waktu Penyelesaian (jam)',
        compute='_compute_resolution_time',
        store=True
    )
    
    follow_up_required = fields.Boolean(
        string='Perlu Follow Up',
        default=False,
        tracking=True
    )

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('classico.complaint') or 'New'
        return super(ClassicoComplaint, self).create(vals)

    @api.depends('incident_datetime', 'resolution_datetime')
    def _compute_resolution_time(self):
        for record in self:
            if record.incident_datetime and record.resolution_datetime:
                delta = record.resolution_datetime - record.incident_datetime
                record.resolution_time = delta.total_seconds() / 3600.0  # Convert to hours
            else:
                record.resolution_time = 0.0

    def action_assign(self):
        """Assign tiket ke penanggung jawab"""
        self.write({'state': 'in_progress'})
        return True

    def action_resolve(self):
        """Tandai tiket sebagai resolved"""
        if not self.resolution_notes:
            raise ValidationError('Catatan penyelesaian wajib diisi sebelum menutup tiket')
        
        self.write({
            'state': 'resolved',
            'resolution_datetime': fields.Datetime.now()
        })
        return True

    def action_close(self):
        """Tutup tiket"""
        if self.state != 'resolved':
            raise ValidationError('Tiket harus diresolve terlebih dahulu sebelum ditutup')
        
        self.write({'state': 'closed'})
        return True

    def action_reopen(self):
        """Buka kembali tiket"""
        self.write({
            'state': 'open',
            'resolution_datetime': False
        })
        return True

    @api.model
    def get_complaint_statistics(self):
        """Statistik keluhan untuk laporan"""
        total = self.search_count([])
        open_count = self.search_count([('state', '=', 'open')])
        in_progress = self.search_count([('state', '=', 'in_progress')])
        resolved = self.search_count([('state', '=', 'resolved')])
        closed = self.search_count([('state', '=', 'closed')])
        
        # Keluhan per kategori
        categories = {}
        for cat in ['food', 'beverage', 'service', 'cleanliness', 'facility', 'other']:
            categories[cat] = self.search_count([('category', '=', cat)])
        
        return {
            'total': total,
            'open': open_count,
            'in_progress': in_progress,
            'resolved': resolved,
            'closed': closed,
            'by_category': categories
        }
