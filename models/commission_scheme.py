# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class CommissionScheme(models.Model):
    _name = 'commission.scheme'
    _description = 'Commission Scheme'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Name', required=True, tracking=True)
    code = fields.Char(string='Code', tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    description = fields.Text(string='Description')
    
    # Rules
    rule_ids = fields.One2many('commission.rule', 'scheme_id', string='Commission Rules')
    rule_count = fields.Integer(compute='_compute_rule_count')
    
    # Configuration
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    
    @api.depends('rule_ids')
    def _compute_rule_count(self):
        for scheme in self:
            scheme.rule_count = len(scheme.rule_ids)
            
    def action_view_rules(self):
        self.ensure_one()
        return {
            'name': _('Commission Rules'),
            'type': 'ir.actions.act_window',
            'res_model': 'commission.rule',
            'view_mode': 'tree,form',
            'domain': [('scheme_id', '=', self.id)],
            'context': {'default_scheme_id': self.id},
        }
    
    def name_get(self):
        result = []
        for scheme in self:
            name = scheme.name
            if scheme.code:
                name = f'[{scheme.code}] {name}'
            result.append((scheme.id, name))
        return result