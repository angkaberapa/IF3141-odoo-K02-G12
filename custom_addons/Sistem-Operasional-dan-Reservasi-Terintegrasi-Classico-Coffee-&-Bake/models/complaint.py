# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ClassicoComplaint(models.Model):
    _name = 'classico.complaint'
    _description = 'Ticketing Keluhan Pelanggan'
    _rec_name = 'title'
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

    title = fields.Char(
        string='Judul Keluhan',
        tracking=True,
        help='Ringkas keluhan untuk identifikasi cepat'
    )

    display_title = fields.Char(
        string='Judul Tampilan',
        compute='_compute_display_title'
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

    partner_id = fields.Many2one(
        'res.partner',
        string='Pelanggan',
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
    ], string='Status', default='open', required=True, tracking=True, group_expand='_group_expand_states')
    
    responsible_division = fields.Selection([
        ('floor', 'Floor Leader (Waiter/Waitress)'),
        ('kitchen', 'Kitchen'),
        ('bar', 'Barista'),
        ('bakery', 'Bakery'),
        ('stock_keeper', 'Stock Keeper'),
        ('cashier', 'Cashier'),
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

    followup_ids = fields.One2many(
        'classico.complaint.followup',
        'complaint_id',
        string='Riwayat Tindak Lanjut'
    )

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for record in self:
            if record.partner_id:
                record.customer_name = record.partner_id.name

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        default_name = self.env.context.get('default_name')
        if default_name and not res.get('title'):
            res['title'] = default_name
            if res.get('name'):
                res['name'] = 'New'
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name') and vals.get('name') != 'New':
                if not vals.get('title'):
                    vals['title'] = vals['name']
                vals['name'] = 'New'
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('classico.complaint') or 'New'
        return super().create(vals_list)

    @api.model
    def name_create(self, name):
        record = self.create({'title': name})
        return record.name_get()[0]

    @api.depends('incident_datetime', 'resolution_datetime')
    def _compute_resolution_time(self):
        for record in self:
            if record.incident_datetime and record.resolution_datetime:
                delta = record.resolution_datetime - record.incident_datetime
                record.resolution_time = delta.total_seconds() / 3600.0  # Convert to hours
            else:
                record.resolution_time = 0.0

    @api.depends('title', 'name')
    def _compute_display_title(self):
        for record in self:
            if record.title and record.title != record.name:
                record.display_title = record.title
            else:
                record.display_title = ''

    @api.model
    def _group_expand_states(self, states, domain, order):
        return ['open', 'in_progress', 'resolved', 'closed']

    def action_assign(self):
        """Assign tiket ke penanggung jawab"""
        for record in self:
            record.write({'state': 'in_progress'})
            record._create_followup('Tiket mulai diproses', 'in_progress')
        return True

    def action_resolve(self):
        """Tandai tiket sebagai resolved"""
        if not self.resolution_notes:
            raise ValidationError('Catatan penyelesaian wajib diisi sebelum menutup tiket')
        
        for record in self:
            record.write({
                'state': 'resolved',
                'resolution_datetime': fields.Datetime.now()
            })
            record._create_followup(record.resolution_notes, 'done')
        return True

    def action_close(self):
        """Tutup tiket"""
        if self.state != 'resolved':
            raise ValidationError('Tiket harus diresolve terlebih dahulu sebelum ditutup')
        
        self.write({'state': 'closed'})
        for record in self:
            record._create_followup('Tiket ditutup', 'done')
        return True

    def action_reopen(self):
        """Buka kembali tiket"""
        self.write({
            'state': 'open',
            'resolution_datetime': False
        })
        for record in self:
            record._create_followup('Tiket dibuka kembali', 'pending')
        return True

    def _create_followup(self, note, status):
        self.ensure_one()
        self.env['classico.complaint.followup'].create({
            'complaint_id': self.id,
            'note': note,
            'status': status,
            'updated_by': self.env.user.id,
        })

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


class ClassicoComplaintFollowup(models.Model):
    _name = 'classico.complaint.followup'
    _description = 'Tindak Lanjut Keluhan'
    _order = 'update_datetime desc'

    complaint_id = fields.Many2one(
        'classico.complaint',
        string='Keluhan',
        required=True,
        ondelete='cascade'
    )
    note = fields.Text(string='Catatan', required=True)
    status = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ], string='Status Tindakan', default='pending', required=True)
    update_datetime = fields.Datetime(string='Waktu Update', default=fields.Datetime.now, required=True)
    updated_by = fields.Many2one('res.users', string='Diperbarui Oleh', default=lambda self: self.env.user, readonly=True)
