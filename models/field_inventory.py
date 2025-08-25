# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import json

class FieldInventory(models.Model):
    _name = 'field.inventory'
    _description = 'Field Inventory Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _rec_name = 'display_name'
    
    # Basic Information
    display_name = fields.Char('Display Name', compute='_compute_display_name', store=True)
    name = fields.Char('Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    sales_rep_id = fields.Many2one('sales.rep', string='Sales Representative', required=True, tracking=True)
    date = fields.Date('Date', required=True, default=fields.Date.today, tracking=True)
    
    # Status and Type
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    inventory_type = fields.Selection([
        ('stock_check', 'Stock Check'),
        ('delivery', 'Delivery'),
        ('return', 'Return'),
        ('transfer', 'Transfer'),
        ('adjustment', 'Adjustment')
    ], string='Inventory Type', required=True, tracking=True)
    
    # Location Information
    location_id = fields.Many2one('stock.location', string='Source Location')
    destination_location_id = fields.Many2one('stock.location', string='Destination Location')
    customer_id = fields.Many2one('res.partner', string='Customer')
    
    # Inventory Lines
    inventory_line_ids = fields.One2many('field.inventory.line', 'inventory_id', string='Inventory Lines')
    
    # Summary Fields
    total_quantity = fields.Float('Total Quantity', compute='_compute_totals', store=True)
    total_value = fields.Monetary('Total Value', compute='_compute_totals', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # GPS and Location
    latitude = fields.Float('Latitude', digits=(10, 7))
    longitude = fields.Float('Longitude', digits=(10, 7))
    address = fields.Char('Address')
    
    # Notes and Comments
    notes = fields.Text('Notes')
    internal_notes = fields.Text('Internal Notes')
    
    @api.depends('name', 'sales_rep_id', 'date', 'inventory_type')
    def _compute_display_name(self):
        for record in self:
            if record.name and record.name != _('New'):
                record.display_name = f"{record.name} - {record.sales_rep_id.name if record.sales_rep_id else ''}"
            else:
                record.display_name = f"{record.inventory_type.title() if record.inventory_type else 'Inventory'} - {record.sales_rep_id.name if record.sales_rep_id else ''}"
    
    @api.depends('inventory_line_ids.quantity', 'inventory_line_ids.unit_price')
    def _compute_totals(self):
        for record in self:
            total_qty = sum(line.quantity for line in record.inventory_line_ids)
            total_val = sum(line.quantity * line.unit_price for line in record.inventory_line_ids)
            record.total_quantity = total_qty
            record.total_value = total_val
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('field.inventory') or _('New')
        return super(FieldInventory, self).create(vals)
    
    def action_confirm(self):
        """Confirm the inventory operation"""
        for record in self:
            if not record.inventory_line_ids:
                raise ValidationError(_("Cannot confirm inventory without lines."))
            record.state = 'confirmed'
            record.message_post(body=_("Inventory operation confirmed."))
    
    def action_start(self):
        """Start the inventory operation"""
        for record in self:
            if record.state != 'confirmed':
                raise ValidationError(_("Only confirmed inventory can be started."))
            record.state = 'in_progress'
            record.message_post(body=_("Inventory operation started."))
    
    def action_complete(self):
        """Complete the inventory operation"""
        for record in self:
            if record.state != 'in_progress':
                raise ValidationError(_("Only in-progress inventory can be completed."))
            record._process_inventory_moves()
            record.state = 'completed'
            record.message_post(body=_("Inventory operation completed."))
    
    def action_cancel(self):
        """Cancel the inventory operation"""
        for record in self:
            if record.state == 'completed':
                raise ValidationError(_("Cannot cancel completed inventory."))
            record.state = 'cancelled'
            record.message_post(body=_("Inventory operation cancelled."))
    
    def _process_inventory_moves(self):
        """Process stock moves based on inventory type"""
        for record in self:
            if record.inventory_type == 'delivery':
                record._create_delivery_moves()
            elif record.inventory_type == 'return':
                record._create_return_moves()
            elif record.inventory_type == 'transfer':
                record._create_transfer_moves()
            elif record.inventory_type == 'adjustment':
                record._create_adjustment_moves()
    
    def _create_delivery_moves(self):
        """Create stock moves for delivery"""
        # Implementation for delivery moves
        pass
    
    def _create_return_moves(self):
        """Create stock moves for returns"""
        # Implementation for return moves
        pass
    
    def _create_transfer_moves(self):
        """Create stock moves for transfers"""
        # Implementation for transfer moves
        pass
    
    def _create_adjustment_moves(self):
        """Create stock moves for adjustments"""
        # Implementation for adjustment moves
        pass

class FieldInventoryLine(models.Model):
    _name = 'field.inventory.line'
    _description = 'Field Inventory Line'
    _order = 'sequence, id'
    
    # Basic Information
    inventory_id = fields.Many2one('field.inventory', string='Inventory', required=True, ondelete='cascade')
    sequence = fields.Integer('Sequence', default=10)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    
    # Quantities
    quantity = fields.Float('Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id', readonly=True)
    
    # Pricing
    unit_price = fields.Monetary('Unit Price', required=True)
    currency_id = fields.Many2one('res.currency', related='inventory_id.currency_id', readonly=True)
    subtotal = fields.Monetary('Subtotal', compute='_compute_subtotal', store=True)
    
    # Stock Information
    lot_id = fields.Many2one('stock.lot', string='Lot/Serial Number')
    expiry_date = fields.Date('Expiry Date')
    
    # Status
    state = fields.Selection(related='inventory_id.state', readonly=True)
    
    # Notes
    notes = fields.Text('Notes')
    
    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.unit_price = self.product_id.list_price
    
    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("Quantity must be positive."))

class FieldInventoryReport(models.Model):
    _name = 'field.inventory.report'
    _description = 'Field Inventory Report'
    _auto = False
    _rec_name = 'date'
    
    # Basic Fields
    date = fields.Date('Date')
    sales_rep_id = fields.Many2one('sales.rep', string='Sales Representative')
    inventory_type = fields.Selection([
        ('stock_check', 'Stock Check'),
        ('delivery', 'Delivery'),
        ('return', 'Return'),
        ('transfer', 'Transfer'),
        ('adjustment', 'Adjustment')
    ], string='Type')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status')
    
    # Product Information
    product_id = fields.Many2one('product.product', string='Product')
    product_category_id = fields.Many2one('product.category', string='Product Category')
    
    # Quantities and Values
    total_quantity = fields.Float('Total Quantity')
    total_value = fields.Monetary('Total Value')
    currency_id = fields.Many2one('res.currency', string='Currency')
    
    # Location
    customer_id = fields.Many2one('res.partner', string='Customer')
    
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    row_number() OVER () AS id,
                    fi.date,
                    fi.sales_rep_id,
                    fi.inventory_type,
                    fi.state,
                    fil.product_id,
                    pt.categ_id AS product_category_id,
                    SUM(fil.quantity) AS total_quantity,
                    SUM(fil.subtotal) AS total_value,
                    fi.currency_id,
                    fi.customer_id
                FROM field_inventory fi
                LEFT JOIN field_inventory_line fil ON fi.id = fil.inventory_id
                LEFT JOIN product_product pp ON fil.product_id = pp.id
                LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                GROUP BY
                    fi.date, fi.sales_rep_id, fi.inventory_type, fi.state,
                    fil.product_id, pt.categ_id, fi.currency_id, fi.customer_id
            )
        """ % self._table)