# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import UserError


CLASSICO_ROLE_SELECTION = [
    ('staff', 'Staf Operasional'),
    ('manager', 'Restaurant Manager'),
    ('admin', 'Administrator Sistem'),
]


class ResUsers(models.Model):
    _inherit = 'res.users'

    classico_role = fields.Selection(
        selection=CLASSICO_ROLE_SELECTION,
        string='Role Classico',
        default='staff',
    )

    def _classico_role_group_commands(self, role):
        group_user = self.env.ref('base.group_user')
        group_system = self.env.ref('base.group_system')
        group_erp_manager = self.env.ref('base.group_erp_manager')

        commands = [
            (4, group_user.id),
            (3, group_system.id),
            (3, group_erp_manager.id),
        ]
        if role in ('manager', 'admin'):
            commands.append((4, group_system.id))
        if role == 'admin':
            commands.append((4, group_erp_manager.id))
        return commands

    def action_apply_classico_role(self, role):
        for user in self:
            user.write({
                'classico_role': role,
                'groups_id': self._classico_role_group_commands(role),
            })

    def _check_classico_user_deletion_allowed(self):
        protected_users = (
            self.env.ref('base.user_admin')
            | self.env.ref('base.user_root')
            | self.env.user
        )
        blocked_users = self & protected_users
        if blocked_users:
            blocked_names = ', '.join(blocked_users.mapped('name'))
            raise UserError(_(
                "Pengguna berikut tidak boleh dihapus: %s. "
                "Admin utama, user sistem, dan user yang sedang login harus tetap ada."
            ) % blocked_names)

    def unlink(self):
        self._check_classico_user_deletion_allowed()
        return super().unlink()

    def action_open_classico_role_assignment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Assign Role',
            'res_model': 'classico.user.role.assignment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_user_id': self.id,
                'default_classico_role': self.classico_role or 'staff',
            },
        }
