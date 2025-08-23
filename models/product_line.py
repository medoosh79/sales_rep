# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ProductLine(models.Model):
    _name = 'product.line'
    _description = 'Product Line'
    _order = 'sequence, name'

    name = fields.Char(
        string='Product Line Name',
        required=True,
        help='Name of the product line'
    )
    
    code = fields.Char(
        string='Code',
        required=True,
        help='Unique code for the product line'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Sequence for ordering'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to hide the product line'
    )
    
    description = fields.Text(
        string='Description',
        help='Description of the product line'
    )
    
    product_ids = fields.Many2many(
        'product.product',
        'product_line_product_rel',
        'line_id',
        'product_id',
        string='Products',
        help='Products included in this line'
    )
    
    # Territory Assignment relationship
    territory_assignment_ids = fields.One2many(
        'territory.assignment',
        'product_line_id',
        string='Territory Assignments',
        help='Territory assignments for this product line'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    
    product_count = fields.Integer(
        string='Product Count',
        compute='_compute_product_count',
        store=True
    )
    
    territory_assignment_count = fields.Integer(
        string='Territory Assignment Count',
        compute='_compute_territory_assignment_count',
        store=True
    )
    
    unique_geo_areas_count = fields.Integer(
        string='Unique Geographic Areas Count',
        compute='_compute_unique_geo_areas_count',
        store=True
    )
    
    unique_sales_reps_count = fields.Integer(
        string='Unique Sales Reps Count',
        compute='_compute_unique_sales_reps_count',
        store=True
    )
    
    @api.depends('product_ids')
    def _compute_product_count(self):
        for record in self:
            record.product_count = len(record.product_ids)
    
    @api.depends('territory_assignment_ids')
    def _compute_territory_assignment_count(self):
        for record in self:
            record.territory_assignment_count = len(record.territory_assignment_ids)
    
    @api.depends('territory_assignment_ids.geo_node_id')
    def _compute_unique_geo_areas_count(self):
        for record in self:
            unique_geo_areas = record.territory_assignment_ids.mapped('geo_node_id')
            record.unique_geo_areas_count = len(unique_geo_areas)
    
    @api.depends('territory_assignment_ids.sales_rep_id')
    def _compute_unique_sales_reps_count(self):
        for record in self:
            unique_sales_reps = record.territory_assignment_ids.mapped('sales_rep_id')
            record.unique_sales_reps_count = len(unique_sales_reps)
    
    @api.constrains('code')
    def _check_unique_code(self):
        for record in self:
            if self.search_count([('code', '=', record.code), ('id', '!=', record.id)]) > 0:
                raise ValidationError('Product line code must be unique!')
    
    def name_get(self):
        result = []
        for record in self:
            name = f'[{record.code}] {record.name}'
            result.append((record.id, name))
        return result
    
    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            records = self.search([('code', operator, name)] + args, limit=limit)
            if not records:
                records = self.search([('name', operator, name)] + args, limit=limit)
        else:
            records = self.search(args, limit=limit)
        return records.name_get()
    
    def action_view_products(self):
        """Action to view products in this line"""
        return {
            'name': 'Products',
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.product_ids.ids)],
            'context': {'default_product_line_ids': [(6, 0, [self.id])]}
        }
    
    def action_view_territory_assignments(self):
        """Action to view territory assignments for this product line"""
        return {
            'name': 'Territory Assignments',
            'type': 'ir.actions.act_window',
            'res_model': 'territory.assignment',
            'view_mode': 'kanban,list,form',
            'domain': [('product_line_id', '=', self.id)],
            'context': {'default_product_line_id': self.id}
        }
    
    def action_view_geo_areas(self):
        """Action to view unique geographic areas covered by this product line"""
        geo_area_ids = self.territory_assignment_ids.mapped('geo_node_id').ids
        return {
            'name': 'Geographic Areas',
            'type': 'ir.actions.act_window',
            'res_model': 'geo.node',
            'view_mode': 'list,form',
            'domain': [('id', 'in', geo_area_ids)],
            'context': {}
        }
    
    def action_view_sales_reps(self):
        """Action to view unique sales representatives for this product line"""
        sales_rep_ids = self.territory_assignment_ids.mapped('sales_rep_id').ids
        return {
            'name': 'Sales Representatives',
            'type': 'ir.actions.act_window',
            'res_model': 'sales.rep',
            'view_mode': 'list,form',
            'domain': [('id', 'in', sales_rep_ids)],
            'context': {}
        }