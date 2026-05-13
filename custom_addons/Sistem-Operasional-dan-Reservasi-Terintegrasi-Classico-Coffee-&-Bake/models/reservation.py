# -*- coding: utf-8 -*-

from itertools import combinations
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import pytz


RESERVATION_BLOCKING_STATES = ['draft', 'confirmed', 'arrived']
RESERVATION_BUFFER_HOURS = 1.0


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
        tracking=True,
        help='Durasi dipakai untuk menghitung bentrok reservasi. Minimal jeda antar reservasi meja adalah 1 jam.'
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
        string='Meja Preferensi',
        tracking=True,
        help='Opsional. Jika meja preferensi tidak memungkinkan, sistem akan menampilkan rekomendasi meja lain.'
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

    recommended_tables_text = fields.Text(
        string='Rekomendasi Meja',
        compute='_compute_recommended_tables_text',
        help='Alternatif kombinasi meja yang memenuhi kapasitas, waktu reservasi, dan jeda minimal 1 jam.'
    )

    recommended_tables_html = fields.Html(
        string='Rekomendasi Meja',
        compute='_compute_recommended_tables_text',
        sanitize=False,
        help='Tampilan rekomendasi meja yang lebih mudah dibaca.'
    )

    buffer_hours = fields.Float(
        string='Jeda Minimum Antar Reservasi (jam)',
        default=RESERVATION_BUFFER_HOURS,
        readonly=True,
        help='Jeda operasional minimum untuk membersihkan dan menyiapkan meja sebelum reservasi berikutnya.'
    )

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for record in self:
            if record.partner_id:
                record.customer_name = record.partner_id.name
                record.customer_phone = record.partner_id.phone or record.partner_id.mobile

    def _float_time_to_local_naive_datetime(self):
        self.ensure_one()
        hour = int(self.reservation_time)
        minute = int(round((self.reservation_time % 1) * 60))
        if minute == 60:
            hour += 1
            minute = 0
        if hour < 0 or hour > 23:
            return False
        return datetime.combine(
            self.reservation_date,
            datetime.min.time().replace(hour=hour, minute=minute)
        )

    def _local_naive_datetime_to_utc_naive(self, local_dt):
        """Konversi tanggal+jam input staf ke UTC untuk disimpan di field Datetime Odoo.

        Field Datetime Odoo disimpan sebagai UTC lalu ditampilkan kembali sesuai timezone user.
        Tanpa konversi ini, input 08:00 WIB akan tersimpan sebagai 08:00 UTC dan tampil sebagai 15:00 WIB.
        """
        tz_name = self.env.context.get('tz') or self.env.user.tz or 'UTC'
        try:
            user_tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            user_tz = pytz.utc
        localized_dt = user_tz.localize(local_dt)
        return localized_dt.astimezone(pytz.utc).replace(tzinfo=None)

    @api.depends('reservation_date', 'reservation_time')
    def _compute_reservation_datetime(self):
        for record in self:
            if record.reservation_date and record.reservation_time is not False:
                local_dt = record._float_time_to_local_naive_datetime()
                record.reservation_datetime = record._local_naive_datetime_to_utc_naive(local_dt) if local_dt else False
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

    @api.depends('reservation_datetime', 'reservation_end_datetime', 'guest_count', 'allocation_ids', 'table_id')
    def _compute_availability_message(self):
        for record in self:
            if not record.reservation_datetime or not record.reservation_end_datetime:
                record.availability_message = 'Tanggal, waktu, dan durasi reservasi belum lengkap'
            else:
                tables = record._get_available_tables()
                capacity = sum(tables.mapped('capacity'))
                if capacity >= record.guest_count:
                    record.availability_message = 'Kapasitas tersedia untuk slot ini'
                else:
                    record.availability_message = 'Kapasitas meja tidak mencukupi untuk slot ini'

    @api.depends('reservation_datetime', 'reservation_end_datetime', 'guest_count', 'table_id')
    def _compute_recommended_tables_text(self):
        for record in self:
            if not record.reservation_datetime or not record.reservation_end_datetime or record.guest_count <= 0:
                text = 'Lengkapi tanggal, waktu, durasi, dan jumlah tamu untuk melihat rekomendasi.'
                record.recommended_tables_text = text
                record.recommended_tables_html = '<div class="text-muted">%s</div>' % text
                continue
            recommendations_text = record._format_table_recommendations(limit=5)
            record.recommended_tables_text = recommendations_text or 'Belum ada kombinasi meja yang memenuhi kapasitas dan jeda minimal 1 jam.'
            record.recommended_tables_html = record._format_table_recommendations_html(limit=5)

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

    @api.constrains('reservation_time', 'duration_hours')
    def _check_reservation_time(self):
        for record in self:
            if record.reservation_time < 7.0 or record.reservation_time > 22.0:
                raise ValidationError('Waktu reservasi harus antara jam 07:00 - 22:00')
            if record.reservation_time + record.duration_hours > 22.0:
                raise ValidationError('Reservasi harus selesai paling lambat pukul 22:00')

    def _get_reservation_buffer_delta(self):
        return timedelta(hours=RESERVATION_BUFFER_HOURS)

    def _get_overlapping_allocations(self, table):
        """Cari alokasi yang bentrok dengan mempertimbangkan buffer 1 jam.

        Reservasi A valid terhadap reservasi B hanya jika ada jeda minimal
        1 jam antara waktu selesai salah satu reservasi dan waktu mulai
        reservasi berikutnya.
        """
        self.ensure_one()
        if not self.reservation_datetime or not self.reservation_end_datetime:
            return self.env['classico.table.allocation']

        buffer_delta = self._get_reservation_buffer_delta()
        return self.env['classico.table.allocation'].search([
            ('table_id', '=', table.id),
            ('reservation_id', '!=', self.id or 0),
            ('state', '=', 'active'),
            ('start_datetime', '<', self.reservation_end_datetime + buffer_delta),
            ('end_datetime', '>', self.reservation_datetime - buffer_delta),
            ('reservation_id.state', 'in', RESERVATION_BLOCKING_STATES),
        ])

    def _get_available_tables(self):
        self.ensure_one()
        tables = self.env['classico.table'].search([('state', '!=', 'unavailable')], order='capacity asc, name asc')
        return tables.filtered(lambda table: not self._get_overlapping_allocations(table))

    def _table_display_name(self, table):
        return table.name if table.name.lower().startswith('meja') else 'Meja %s' % table.name

    def _table_combination_label(self, tables):
        total_capacity = sum(tables.mapped('capacity'))
        table_names = ', '.join([self._table_display_name(table) for table in tables])
        return '%s (kapasitas total %s)' % (table_names, total_capacity)

    def _get_table_recommendations(self, limit=5):
        self.ensure_one()
        available_tables = list(self._get_available_tables())
        if not available_tables:
            return []

        recommendations = []
        max_combination_size = min(len(available_tables), 4)
        for size in range(1, max_combination_size + 1):
            for combo in combinations(available_tables, size):
                table_set = self.env['classico.table'].browse([table.id for table in combo])
                total_capacity = sum(table_set.mapped('capacity'))
                if total_capacity >= self.guest_count:
                    recommendations.append((table_set, total_capacity))
            if recommendations:
                break

        recommendations.sort(key=lambda item: (item[1], len(item[0]), ','.join(item[0].mapped('name'))))
        return [tables for tables, capacity in recommendations[:limit]]

    def _format_table_recommendations(self, limit=5):
        self.ensure_one()
        recommendations = self._get_table_recommendations(limit=limit)
        return '\n'.join(['%s. %s' % (index, self._table_combination_label(tables)) for index, tables in enumerate(recommendations, start=1)])

    def _format_table_recommendations_html(self, limit=5):
        self.ensure_one()
        recommendations = self._get_table_recommendations(limit=limit)
        if not recommendations:
            return '''
                <div class="alert alert-warning mb-0" role="alert">
                    Belum ada kombinasi meja yang memenuhi kapasitas, slot waktu, dan jeda minimal 1 jam.
                </div>
            '''

        rows = []
        for index, tables in enumerate(recommendations, start=1):
            total_capacity = sum(tables.mapped('capacity'))
            table_badges = ''.join([
                '<span class="badge rounded-pill text-bg-light border me-1 mb-1">%s · %s kursi</span>' % (
                    self._table_display_name(table),
                    table.capacity,
                )
                for table in tables
            ])
            rows.append('''
                <tr>
                    <td class="text-muted" style="width: 40px;">%s</td>
                    <td>%s</td>
                    <td class="text-end" style="white-space: nowrap;"><strong>%s kursi</strong></td>
                </tr>
            ''' % (index, table_badges, total_capacity))

        return '''
            <div class="border rounded p-2 bg-light">
                <div class="fw-bold mb-2">Kombinasi meja yang memungkinkan</div>
                <table class="table table-sm table-borderless mb-0">
                    <tbody>%s</tbody>
                </table>
                <small class="text-muted">Rekomendasi sudah memperhitungkan kapasitas, jadwal bentrok, dan jeda minimal 1 jam.</small>
            </div>
        ''' % ''.join(rows)

    def _raise_no_capacity_error(self, prefix=None):
        self.ensure_one()
        recommendations = self._format_table_recommendations(limit=5)
        message = prefix or 'Tidak ada kapasitas meja yang mencukupi untuk reservasi ini.'
        if recommendations:
            message += '\n\nRekomendasi meja yang memungkinkan:\n%s' % recommendations
        else:
            message += '\n\nTidak ada rekomendasi meja yang memenuhi kapasitas, slot waktu, dan jeda minimal 1 jam.'
        raise ValidationError(message)

    def _select_tables_for_capacity(self):
        self.ensure_one()
        if not self.reservation_datetime or not self.reservation_end_datetime:
            raise ValidationError('Lengkapi tanggal, waktu, dan durasi reservasi terlebih dahulu')

        if self.table_id:
            if self.table_id.state == 'unavailable':
                self._raise_no_capacity_error('Meja preferensi sedang tidak tersedia.')
            if self._get_overlapping_allocations(self.table_id):
                self._raise_no_capacity_error('Meja preferensi sudah memiliki reservasi lain pada slot tersebut atau jeda 1 jam tidak terpenuhi.')
            if self.table_id.capacity >= self.guest_count:
                return self.table_id

            recommendations = self._get_table_recommendations(limit=5)
            if recommendations:
                raise ValidationError(
                    'Kapasitas meja preferensi (%s kursi) tidak mencukupi untuk %s tamu.\n\n'
                    'Rekomendasi meja yang memungkinkan:\n%s' % (
                        self.table_id.capacity,
                        self.guest_count,
                        self._format_table_recommendations(limit=5)
                    )
                )
            self._raise_no_capacity_error('Kapasitas meja preferensi tidak mencukupi.')

        recommendations = self._get_table_recommendations(limit=1)
        if not recommendations:
            self._raise_no_capacity_error('Tidak ada kapasitas meja yang mencukupi untuk reservasi ini.')
        return recommendations[0]

    def action_check_availability(self):
        for record in self:
            recommendations = record._format_table_recommendations(limit=5)
            if not recommendations:
                record._raise_no_capacity_error('Slot ini belum memiliki kombinasi meja yang memungkinkan.')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Kapasitas tersedia',
                    'message': 'Rekomendasi meja:\n%s' % recommendations,
                    'sticky': False,
                    'type': 'success',
                }
            }
        return True

    def action_allocate_tables(self):
        for record in self:
            if record.state in ['done', 'cancelled']:
                raise ValidationError('Reservasi yang sudah selesai atau dibatalkan tidak dapat dialokasikan ulang')

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
            # Reservasi masa depan tidak mengubah status fisik meja. Status meja tetap
            # merepresentasikan kondisi real-time di lantai restoran.
            record.table_id = selected_tables[:1].id if selected_tables else False
        return True

    def action_confirm(self):
        """Konfirmasi reservasi dan langsung alokasikan meja."""
        for record in self:
            if not record.allocation_ids.filtered(lambda allocation: allocation.state == 'active'):
                record.action_allocate_tables()
            if record.allocated_capacity < record.guest_count:
                raise ValidationError('Kapasitas alokasi meja belum mencukupi jumlah tamu')
            record.write({'state': 'confirmed'})
        return True

    def action_arrive(self):
        """Tandai pelanggan sudah datang dan ubah status fisik meja menjadi terisi."""
        self.write({'state': 'arrived'})
        self.mapped('table_ids').write({
            'state': 'occupied',
            'last_updated': fields.Datetime.now(),
            'updated_by': self.env.user.id,
        })
        return True

    def action_done(self):
        """Selesaikan reservasi dan lepaskan alokasi meja."""
        tables = self.mapped('table_ids')
        self.write({'state': 'done'})
        self.mapped('allocation_ids').filtered(lambda allocation: allocation.state == 'active').write({'state': 'released'})
        # Waiter tetap dapat mengubah manual, tetapi default saat reservasi selesai adalah meja tersedia kembali.
        tables.write({
            'state': 'available',
            'last_updated': fields.Datetime.now(),
            'updated_by': self.env.user.id,
        })
        return True

    def action_cancel(self):
        """Batalkan reservasi tanpa memaksa perubahan status fisik meja."""
        self.write({'state': 'cancelled'})
        self.mapped('allocation_ids').filtered(lambda allocation: allocation.state == 'active').write({'state': 'cancelled'})
        return True

    def action_reset_to_draft(self):
        """Kembalikan ke draft."""
        self.write({'state': 'draft'})
        return True
