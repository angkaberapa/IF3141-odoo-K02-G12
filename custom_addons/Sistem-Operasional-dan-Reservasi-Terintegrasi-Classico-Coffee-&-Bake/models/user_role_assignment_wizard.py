# -*- coding: utf-8 -*-

from odoo import api, fields, models

from .res_users import CLASSICO_ROLE_SELECTION


class ClassicoUserRoleAssignmentWizard(models.TransientModel):
    _name = 'classico.user.role.assignment.wizard'
    _description = 'Wizard Assign Role Pengguna Classico'

    user_id = fields.Many2one(
        'res.users',
        string='Pengguna',
        required=True,
        domain=[('share', '=', False)],
    )
    login = fields.Char(string='Login', related='user_id.login', readonly=True)
    active = fields.Boolean(string='Aktif', related='user_id.active', readonly=True)
    classico_role = fields.Selection(
        selection=CLASSICO_ROLE_SELECTION,
        string='Role',
        required=True,
        default='staff',
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        user_id = values.get('user_id')
        if user_id and not values.get('classico_role'):
            user = self.env['res.users'].browse(user_id)
            values['classico_role'] = user.classico_role or 'staff'
        return values

    def action_confirm(self):
        self.ensure_one()
        self.user_id.sudo().action_apply_classico_role(self.classico_role)
        return {'type': 'ir.actions.act_window_close'}
