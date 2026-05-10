# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import ValidationError

from .res_users import CLASSICO_ROLE_SELECTION


class ClassicoUserCreateWizard(models.TransientModel):
    _name = 'classico.user.create.wizard'
    _description = 'Wizard Tambah Pengguna Classico'

    name = fields.Char(string='Nama Pengguna', required=True)
    login = fields.Char(string='Login', required=True)
    password = fields.Char(string='Password', required=True)
    password_confirmation = fields.Char(string='Konfirmasi Password', required=True)
    active = fields.Boolean(string='Aktif', default=True)
    classico_role = fields.Selection(
        selection=CLASSICO_ROLE_SELECTION,
        string='Role',
        required=True,
        default='staff',
    )

    def _prepare_user_values(self):
        self.ensure_one()
        login = (self.login or '').strip()
        name = (self.name or '').strip()

        if not name:
            raise ValidationError(_('Nama pengguna wajib diisi.'))
        if not login:
            raise ValidationError(_('Login wajib diisi.'))
        if self.password != self.password_confirmation:
            raise ValidationError(_('Konfirmasi password tidak cocok.'))
        if self.env['res.users'].sudo().search_count([('login', '=', login)]):
            raise ValidationError(_('Login sudah digunakan. Gunakan login lain.'))

        company_ids = self.env.user.company_ids.ids or [self.env.company.id]
        return {
            'name': name,
            'login': login,
            'password': self.password,
            'active': self.active,
            'share': False,
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, company_ids)],
            'classico_role': self.classico_role,
        }

    def action_confirm(self):
        self.ensure_one()
        user = self.env['res.users'].sudo().create(self._prepare_user_values())
        user.sudo().action_apply_classico_role(self.classico_role)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Assign Role',
            'res_model': 'res.users',
            'view_mode': 'form',
            'res_id': user.id,
            'target': 'current',
        }
