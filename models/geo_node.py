# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class GeoNode(models.Model):
    _name = 'geo.node'
    _description = 'Geographic Node'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'
    
    name = fields.Char(string='Name', required=True, tracking=True)
    complete_name = fields.Char(string='Complete Name', compute='_compute_complete_name', store=True)
    code = fields.Char(string='Code', tracking=True, help='Auto-generated sequential code based on hierarchy')
    active = fields.Boolean(default=True, tracking=True)
    
    # Hierarchy fields
    type = fields.Selection([
        ('country', 'Country'),
        ('region', 'Region/State'),
        ('governorate', 'Governorate/Province'),
        ('city', 'City'),
        ('district', 'District'),
        ('zone', 'Zone'),
        ('neighborhood', 'Neighborhood'),
        ('block', 'Block/Street'),
    ], string='Type', required=True, default='country', tracking=True)
    
    parent_id = fields.Many2one('geo.node', string='Parent Node', index=True, ondelete='cascade',
                              domain="[('type', '!=', 'block')]",
                              tracking=True)
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('geo.node', 'parent_id', string='Child Nodes')
    
    # Additional information
    description = fields.Text(string='Description')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    
    # Territory Coverage relationship
    territory_assignment_ids = fields.One2many(
        'territory.assignment',
        'geo_node_id',
        string='Territory Assignments',
        help='Territory assignments for this geographic area'
    )
    
    # Statistics
    partner_count = fields.Integer(string='Partners', compute='_compute_partner_count')
    assignment_count = fields.Integer(string='Assignments', compute='_compute_assignment_count')
    territory_assignment_count = fields.Integer(
        string='Territory Assignment Count',
        compute='_compute_territory_assignment_count',
        store=True
    )
    
    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for node in self:
            if node.parent_id:
                node.complete_name = '%s / %s' % (node.parent_id.complete_name, node.name)
            else:
                node.complete_name = node.name
    
    @api.constrains('parent_id', 'type')
    def _check_hierarchy(self):
        # Define the hierarchy order
        hierarchy_order = {
            'country': 0,
            'region': 1,
            'governorate': 2,
            'city': 3,
            'district': 4,
            'zone': 5,
            'neighborhood': 6,
            'block': 7,
        }
        
        # Define valid parent-child relationships
        valid_parents = {
            'country': [],  # Country has no parent
            'region': ['country'],
            'governorate': ['region', 'country'],
            'city': ['governorate', 'region', 'country'],
            'district': ['city'],
            'zone': ['district', 'city'],
            'neighborhood': ['zone', 'district'],
            'block': ['neighborhood'],
        }
        
        for node in self:
            if node.parent_id:
                # Check if parent type is valid for this node type
                if node.parent_id.type not in valid_parents.get(node.type, []):
                    valid_parent_types = ', '.join([dict(node._fields['type'].selection)[t] for t in valid_parents.get(node.type, [])])
                    raise ValidationError(_('Invalid hierarchy: %s cannot be a child of %s.\n\nCorrect hierarchy order: Country → Region/State → Governorate/Province → City → District → Zone → Neighborhood → Block/Street\n\nValid parent types for %s: %s') % 
                                        (dict(node._fields['type'].selection)[node.type],
                                         dict(node._fields['type'].selection)[node.parent_id.type],
                                         dict(node._fields['type'].selection)[node.type],
                                         valid_parent_types or 'None (top level only)'))
                
                # Check hierarchy order (parent must be higher in hierarchy)
                parent_order = hierarchy_order.get(node.parent_id.type, 999)
                child_order = hierarchy_order.get(node.type, 999)
                if parent_order >= child_order:
                    raise ValidationError(_('Invalid hierarchy order: %s must be higher than %s in the hierarchy.') % 
                                        (dict(node._fields['type'].selection)[node.parent_id.type],
                                         dict(node._fields['type'].selection)[node.type]))
            else:
                # Only country can be at the top level
                if node.type != 'country':
                    raise ValidationError(_('Only Country nodes can be at the top level. %s must have a parent.') % 
                                        dict(node._fields['type'].selection)[node.type])
    
    def _compute_partner_count(self):
        # This will be implemented in later phases with actual partner data
        for node in self:
            node.partner_count = 0
    
    def _compute_assignment_count(self):
        # Count sales rep assignments for this geographic node
        assignment_data = self.env['sales.rep.assignment'].read_group(
            [('geo_node_id', 'in', self.ids)],
            ['geo_node_id'], ['geo_node_id'])
        
        assignment_dict = {data['geo_node_id'][0]: data['geo_node_id_count'] 
                          for data in assignment_data}
        
        for node in self:
            node.assignment_count = assignment_dict.get(node.id, 0)
    
    @api.depends('territory_assignment_ids')
    def _compute_territory_assignment_count(self):
        for node in self:
            node.territory_assignment_count = len(node.territory_assignment_ids)
            
    def action_view_assignments(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("sales_rep_mgmt_pro.action_sales_rep_assignment")
        action['domain'] = [('geo_node_id', '=', self.id)]
        action['context'] = {'default_geo_node_id': self.id}
        return action
        
    def action_view_partners(self):
        self.ensure_one()
        # This will be implemented in later phases with actual partner integration
        return {
            'name': _('Partners'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'tree,form',
            'domain': [],  # Will be updated in future phases
            'context': {},
        }
    
    @api.model
    def create(self, vals):
        # Auto-generate code if not provided
        if not vals.get('code'):
            vals['code'] = self._generate_sequential_code(vals.get('parent_id'), vals.get('type'))
        return super(GeoNode, self).create(vals)
    
    def write(self, vals):
        # Regenerate code if parent changes
        if 'parent_id' in vals and not vals.get('code'):
            for record in self:
                vals['code'] = self._generate_sequential_code(vals.get('parent_id', record.parent_id.id), vals.get('type', record.type))
        return super(GeoNode, self).write(vals)
    
    def _generate_sequential_code(self, parent_id, node_type):
        """Generate sequential code based on parent hierarchy"""
        if not parent_id:
            # For top-level (country) nodes, use simple sequential numbering
            last_code = self.search([('parent_id', '=', False), ('type', '=', node_type)], 
                                  order='code desc', limit=1)
            if last_code and last_code.code and last_code.code.isdigit():
                return str(int(last_code.code) + 1).zfill(2)
            else:
                return '01'
        else:
            # For child nodes, use parent code + sequential number
            parent = self.browse(parent_id)
            if not parent.exists():
                return '001'
            
            parent_code = parent.code or '00'
            
            # Find the last child with the same parent and type
            siblings = self.search([
                ('parent_id', '=', parent_id),
                ('type', '=', node_type)
            ], order='code desc', limit=1)
            
            if siblings and siblings.code:
                # Extract the last part of the code (after parent code)
                try:
                    if siblings.code.startswith(parent_code):
                        last_number = int(siblings.code[len(parent_code):])
                        next_number = last_number + 1
                    else:
                        next_number = 1
                except (ValueError, IndexError):
                    next_number = 1
            else:
                next_number = 1
            
            # Generate new code: parent_code + sequential_number
            return parent_code + str(next_number).zfill(2)
    
    def action_fix_hierarchy(self):
        """Fix hierarchy issues by reorganizing nodes according to proper structure"""
        self.ensure_one()
        
        # If this is a region trying to be under a zone, we need to fix it
        if self.type == 'region' and self.parent_id and self.parent_id.type == 'zone':
            # Find or create a country for this region
            country = self.env['geo.node'].search([
                ('type', '=', 'country'),
                ('name', 'ilike', 'المملكة العربية السعودية')
            ], limit=1)
            
            if not country:
                # Create a default country
                country = self.env['geo.node'].create({
                    'name': 'المملكة العربية السعودية',
                    'type': 'country',
                    'code': '01'
                })
            
            # Move this region under the country
            self.write({
                'parent_id': country.id,
                'code': False  # Will be regenerated
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Hierarchy Fixed'),
                    'message': _('The geographic hierarchy has been corrected.'),
                    'type': 'success',
                }
            }
    
    @api.model
    def fix_all_hierarchy_issues(self):
        """Fix all hierarchy issues in the database"""
        # Find all regions that are incorrectly placed
        problematic_regions = self.search([
            ('type', '=', 'region'),
            ('parent_id.type', '!=', 'country')
        ])
        
        # Find or create a default country
        country = self.search([('type', '=', 'country')], limit=1)
        if not country:
            country = self.create({
                'name': 'المملكة العربية السعودية',
                'type': 'country',
                'code': '01'
            })
        
        # Move all problematic regions under the country
        for region in problematic_regions:
            region.write({
                'parent_id': country.id,
                'code': False  # Will be regenerated
            })
        
        # Fix other hierarchy issues
        # Zones should be under districts or cities
        problematic_zones = self.search([
            ('type', '=', 'zone'),
            ('parent_id.type', 'not in', ['district', 'city'])
        ])
        
        for zone in problematic_zones:
            # Try to find a suitable parent (district or city)
            suitable_parent = self.search([
                ('type', 'in', ['district', 'city']),
                ('name', 'ilike', zone.name[:10])  # Try to match by name similarity
            ], limit=1)
            
            if not suitable_parent:
                # Create a default city under the country
                suitable_parent = self.create({
                    'name': 'مدينة افتراضية',
                    'type': 'city',
                    'parent_id': country.id
                })
            
            zone.write({
                'parent_id': suitable_parent.id,
                'code': False  # Will be regenerated
            })
        
        return len(problematic_regions) + len(problematic_zones)
    
    @api.constrains('code')
    def _check_code_unique(self):
        for node in self:
            if node.code:
                domain = [('code', '=', node.code), ('id', '!=', node.id)]
                if self.search_count(domain):
                    raise ValidationError(_('Geographic node code must be unique!'))