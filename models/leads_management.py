# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class LeadSource(models.Model):
    _name = 'lead.source'
    _description = 'Lead Source'
    _order = 'sequence, name'

    name = fields.Char('Source Name', required=True)
    code = fields.Char('Source Code', required=True)
    description = fields.Text('Description')
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    color = fields.Integer('Color Index', default=0)
    
    # Statistics
    lead_count = fields.Integer('Lead Count', compute='_compute_lead_count')
    conversion_rate = fields.Float('Conversion Rate (%)', compute='_compute_conversion_rate')
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Source code must be unique!'),
    ]
    
    def _compute_lead_count(self):
        for source in self:
            source.lead_count = self.env['sales.lead'].search_count([('source_id', '=', source.id)])
    
    def _compute_conversion_rate(self):
        for source in self:
            total_leads = self.env['sales.lead'].search_count([('source_id', '=', source.id)])
            converted_leads = self.env['sales.lead'].search_count([
                ('source_id', '=', source.id),
                ('stage_id.is_won', '=', True)
            ])
            source.conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0.0
    
    def action_view_leads(self):
        """View leads for this source"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Leads from %s') % self.name,
            'res_model': 'sales.lead',
            'view_mode': 'list,form',
            'domain': [('source_id', '=', self.id)],
            'context': {'default_source_id': self.id},
        }
    
    def action_view_conversion_rate(self):
        """View conversion rate details for this source"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Conversion Rate for %s') % self.name,
            'res_model': 'sales.lead',
            'view_mode': 'list,form',
            'domain': [('source_id', '=', self.id), ('stage_id.is_won', '=', True)],
            'context': {'default_source_id': self.id},
        }


class LeadStage(models.Model):
    _name = 'lead.stage'
    _description = 'Lead Stage'
    _order = 'sequence, name'

    name = fields.Char('Stage Name', required=True)
    description = fields.Text('Description')
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    
    # Stage Properties
    is_won = fields.Boolean('Is Won Stage', help='Leads in this stage are considered won/converted')
    is_lost = fields.Boolean('Is Lost Stage', help='Leads in this stage are considered lost')
    fold = fields.Boolean('Folded in Kanban', help='This stage is folded in the kanban view when there are no records in that stage to display.')
    
    # Automation
    auto_assign_sales_rep = fields.Boolean('Auto Assign Sales Rep', help='Automatically assign a sales rep when lead reaches this stage')
    send_email_notification = fields.Boolean('Send Email Notification', help='Send email notification when lead reaches this stage')
    
    # Statistics
    lead_count = fields.Integer('Lead Count', compute='_compute_lead_count')
    
    def _compute_lead_count(self):
        for stage in self:
            stage.lead_count = self.env['sales.lead'].search_count([('stage_id', '=', stage.id)])
    
    def action_view_stage_leads(self):
        """View leads in this stage"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Leads in %s') % self.name,
            'res_model': 'sales.lead',
            'view_mode': 'list,form',
            'domain': [('stage_id', '=', self.id)],
            'context': {'default_stage_id': self.id},
        }


class SalesLead(models.Model):
    _name = 'sales.lead'
    _description = 'Sales Lead'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, date_created desc, id desc'

    name = fields.Char('Lead Name', required=True, tracking=True)
    
    # Contact Information
    contact_name = fields.Char('Contact Name', required=True, tracking=True)
    email = fields.Char('Email', tracking=True)
    phone = fields.Char('Phone', tracking=True)
    mobile = fields.Char('Mobile', tracking=True)
    
    # Company Information
    company_name = fields.Char('Company Name', tracking=True)
    website = fields.Char('Website')
    industry_id = fields.Many2one('res.partner.industry', string='Industry')
    
    # Address
    street = fields.Char('Street')
    street2 = fields.Char('Street2')
    city = fields.Char('City')
    state_id = fields.Many2one('res.country.state', string='State')
    country_id = fields.Many2one('res.country', string='Country')
    zip = fields.Char('ZIP')
    
    # Lead Details
    source_id = fields.Many2one('lead.source', string='Lead Source', required=True, tracking=True)
    stage_id = fields.Many2one('lead.stage', string='Stage', required=True, tracking=True, group_expand='_read_group_stage_ids')
    sales_rep_id = fields.Many2one('sales.rep', string='Assigned Sales Rep', tracking=True)
    territory_id = fields.Many2one('territory.assignment', string='Territory', compute='_compute_territory_id', store=True)
    
    # Qualification
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Very High')
    ], string='Priority', default='1', tracking=True)
    
    qualification_score = fields.Integer('Qualification Score', default=0, help='Score from 0-100 based on qualification criteria')
    budget = fields.Float('Estimated Budget')
    expected_revenue = fields.Float('Expected Revenue', tracking=True)
    probability = fields.Float('Success Probability (%)', default=10.0, tracking=True)
    
    # Timeline
    date_created = fields.Datetime('Created Date', default=fields.Datetime.now, readonly=True)
    date_assigned = fields.Datetime('Assigned Date', readonly=True)
    expected_closing = fields.Date('Expected Closing Date', tracking=True)
    date_converted = fields.Datetime('Converted Date', readonly=True)
    date_lost = fields.Datetime('Lost Date', readonly=True)
    
    # Status
    active = fields.Boolean('Active', default=True)
    is_qualified = fields.Boolean('Is Qualified', compute='_compute_is_qualified', store=True)
    
    # Conversion
    partner_id = fields.Many2one('res.partner', string='Converted Customer', readonly=True)
    opportunity_id = fields.Many2one('crm.lead', string='Converted Opportunity', readonly=True)
    
    # Additional Information
    description = fields.Text('Description')
    notes = fields.Text('Internal Notes')
    tags = fields.Char('Tags')
    
    # Communication
    last_contact_date = fields.Date('Last Contact Date')
    next_contact_date = fields.Date('Next Contact Date')
    contact_count = fields.Integer('Contact Count', default=0)
    
    # Company
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', related='company_id.currency_id')
    
    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        """Read group customization for stage_id field"""
        stage_ids = self.env['lead.stage'].search([])
        return stage_ids
    
    @api.depends('qualification_score')
    def _compute_is_qualified(self):
        for lead in self:
            lead.is_qualified = lead.qualification_score >= 60  # 60% threshold for qualification
    
    @api.depends('sales_rep_id')
    def _compute_territory_id(self):
        for lead in self:
            if lead.sales_rep_id and lead.sales_rep_id.territory_assignment_ids:
                # Get the first active territory assignment
                territory = lead.sales_rep_id.territory_assignment_ids.filtered(lambda t: t.active)[:1]
                lead.territory_id = territory.id if territory else False
            else:
                lead.territory_id = False
    
    @api.onchange('stage_id')
    def _onchange_stage_id(self):
        if self.stage_id:
            if self.stage_id.is_won:
                self.probability = 100.0
            elif self.stage_id.is_lost:
                self.probability = 0.0
    
    @api.model
    def create(self, vals):
        lead = super().create(vals)
        
        # Auto-assign sales rep if stage requires it
        if lead.stage_id.auto_assign_sales_rep and not lead.sales_rep_id:
            lead._auto_assign_sales_rep()
        
        # Send notification if required
        if lead.stage_id.send_email_notification:
            lead._send_stage_notification()
        
        return lead
    
    def write(self, vals):
        old_stage = self.stage_id
        result = super().write(vals)
        
        # Handle stage changes
        if 'stage_id' in vals:
            new_stage = self.env['lead.stage'].browse(vals['stage_id'])
            self._handle_stage_change(old_stage, new_stage)
        
        # Handle sales rep assignment
        if 'sales_rep_id' in vals and vals['sales_rep_id']:
            self.write({'date_assigned': fields.Datetime.now()})
        
        return result
    
    def _handle_stage_change(self, old_stage, new_stage):
        """Handle actions when stage changes"""
        for lead in self:
            # Auto-assign sales rep if required
            if new_stage.auto_assign_sales_rep and not lead.sales_rep_id:
                lead._auto_assign_sales_rep()
            
            # Send notification if required
            if new_stage.send_email_notification:
                lead._send_stage_notification()
            
            # Mark as converted if won stage
            if new_stage.is_won and not lead.date_converted:
                lead.date_converted = fields.Datetime.now()
            
            # Mark as lost if lost stage
            if new_stage.is_lost and not lead.date_lost:
                lead.date_lost = fields.Datetime.now()
    
    def _auto_assign_sales_rep(self):
        """Auto-assign sales rep based on territory or workload"""
        for lead in self:
            # Try to find sales rep by territory first
            if lead.state_id:
                territory = self.env['territory.assignment'].search([
                    ('state_ids', 'in', [lead.state_id.id]),
                    ('active', '=', True)
                ], limit=1)
                
                if territory and territory.sales_rep_id:
                    lead.sales_rep_id = territory.sales_rep_id
                    continue
            
            # If no territory match, assign to sales rep with least workload
            sales_reps = self.env['sales.rep'].search([('active', '=', True)])
            if sales_reps:
                # Count current leads per sales rep
                lead_counts = {}
                for rep in sales_reps:
                    lead_counts[rep.id] = self.search_count([
                        ('sales_rep_id', '=', rep.id),
                        ('stage_id.is_won', '=', False),
                        ('stage_id.is_lost', '=', False)
                    ])
                
                # Assign to rep with minimum leads
                min_rep_id = min(lead_counts, key=lead_counts.get)
                lead.sales_rep_id = min_rep_id
    
    def _send_stage_notification(self):
        """Send email notification for stage change"""
        for lead in self:
            if lead.sales_rep_id and lead.sales_rep_id.user_id:
                lead.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=lead.sales_rep_id.user_id.id,
                    summary=_('Lead Stage Changed'),
                    note=_('Lead %s has moved to stage %s') % (lead.name, lead.stage_id.name)
                )
    
    def action_qualify_lead(self):
        """Qualify the lead"""
        for lead in self:
            if lead.qualification_score < 60:
                raise UserError(_('Lead must have a qualification score of at least 60% to be qualified.'))
            
            # Move to qualified stage
            qualified_stage = self.env['lead.stage'].search([('name', 'ilike', 'qualified')], limit=1)
            if qualified_stage:
                lead.stage_id = qualified_stage
            
            lead.message_post(
                body=_('Lead has been qualified with score: %s%%') % lead.qualification_score,
                message_type='notification'
            )
    
    def action_convert_to_customer(self):
        """Convert lead to customer"""
        for lead in self:
            if lead.partner_id:
                raise UserError(_('Lead is already converted to customer.'))
            
            # Create customer
            partner_vals = {
                'name': lead.company_name or lead.contact_name,
                'is_company': bool(lead.company_name),
                'email': lead.email,
                'phone': lead.phone,
                'mobile': lead.mobile,
                'website': lead.website,
                'industry_id': lead.industry_id.id if lead.industry_id else False,
                'street': lead.street,
                'street2': lead.street2,
                'city': lead.city,
                'state_id': lead.state_id.id if lead.state_id else False,
                'country_id': lead.country_id.id if lead.country_id else False,
                'zip': lead.zip,
                'customer_rank': 1,
            }
            
            partner = self.env['res.partner'].create(partner_vals)
            lead.partner_id = partner
            
            # Move to won stage
            won_stage = self.env['lead.stage'].search([('is_won', '=', True)], limit=1)
            if won_stage:
                lead.stage_id = won_stage
            
            lead.message_post(
                body=_('Lead converted to customer: %s') % partner.name,
                message_type='notification'
            )
            
            return {
                'type': 'ir.actions.act_window',
                'name': _('Customer'),
                'res_model': 'res.partner',
                'res_id': partner.id,
                'view_mode': 'form',
                'target': 'current',
            }
    
    def action_convert_to_opportunity(self):
        """Convert lead to CRM opportunity"""
        for lead in self:
            if lead.opportunity_id:
                raise UserError(_('Lead is already converted to opportunity.'))
            
            # Create CRM lead (opportunity)
            opportunity_vals = {
                'name': lead.name,
                'contact_name': lead.contact_name,
                'email_from': lead.email,
                'phone': lead.phone,
                'mobile': lead.mobile,
                'partner_name': lead.company_name,
                'website': lead.website,
                'street': lead.street,
                'street2': lead.street2,
                'city': lead.city,
                'state_id': lead.state_id.id if lead.state_id else False,
                'country_id': lead.country_id.id if lead.country_id else False,
                'zip': lead.zip,
                'user_id': lead.sales_rep_id.user_id.id if lead.sales_rep_id and lead.sales_rep_id.user_id else False,
                'expected_revenue': lead.expected_revenue,
                'probability': lead.probability,
                'date_deadline': lead.expected_closing,
                'description': lead.description,
            }
            
            opportunity = self.env['crm.lead'].create(opportunity_vals)
            lead.opportunity_id = opportunity
            
            # Move to converted stage
            converted_stage = self.env['lead.stage'].search([('is_won', '=', True)], limit=1)
            if converted_stage:
                lead.stage_id = converted_stage
            
            lead.message_post(
                body=_('Lead converted to opportunity: %s') % opportunity.name,
                message_type='notification'
            )
            
            return {
                'type': 'ir.actions.act_window',
                'name': _('Opportunity'),
                'res_model': 'crm.lead',
                'res_id': opportunity.id,
                'view_mode': 'form',
                'target': 'current',
            }
    
    def action_mark_lost(self):
        """Mark lead as lost"""
        for lead in self:
            lost_stage = self.env['lead.stage'].search([('is_lost', '=', True)], limit=1)
            if lost_stage:
                lead.stage_id = lost_stage
            
            lead.message_post(
                body=_('Lead marked as lost'),
                message_type='notification'
            )
    
    def action_schedule_activity(self):
        """Schedule follow-up activity"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Schedule Activity'),
            'res_model': 'mail.activity',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_id': self.id,
                'default_res_model': 'sales.lead',
                'default_user_id': self.sales_rep_id.user_id.id if self.sales_rep_id and self.sales_rep_id.user_id else self.env.user.id,
            }
        }


class LeadQualificationCriteria(models.Model):
    _name = 'lead.qualification.criteria'
    _description = 'Lead Qualification Criteria'
    _order = 'sequence, name'

    name = fields.Char('Criteria Name', required=True)
    description = fields.Text('Description')
    sequence = fields.Integer('Sequence', default=10)
    weight = fields.Float('Weight (%)', default=10.0, help='Weight of this criteria in overall qualification score')
    active = fields.Boolean('Active', default=True)
    
    # Criteria Type
    criteria_type = fields.Selection([
        ('budget', 'Budget'),
        ('authority', 'Decision Authority'),
        ('need', 'Need/Pain Point'),
        ('timeline', 'Timeline'),
        ('fit', 'Product Fit'),
        ('engagement', 'Engagement Level'),
        ('other', 'Other')
    ], string='Criteria Type', required=True)
    
    _sql_constraints = [
        ('weight_positive', 'CHECK(weight >= 0)', 'Weight must be positive!'),
        ('weight_max', 'CHECK(weight <= 100)', 'Weight cannot exceed 100%!'),
    ]


class LeadQualificationScore(models.Model):
    _name = 'lead.qualification.score'
    _description = 'Lead Qualification Score'

    lead_id = fields.Many2one('sales.lead', string='Lead', required=True, ondelete='cascade')
    criteria_id = fields.Many2one('lead.qualification.criteria', string='Criteria', required=True)
    score = fields.Float('Score (0-10)', default=0.0, help='Score from 0 to 10 for this criteria')
    notes = fields.Text('Notes')
    
    _sql_constraints = [
        ('score_range', 'CHECK(score >= 0 AND score <= 10)', 'Score must be between 0 and 10!'),
        ('unique_lead_criteria', 'unique(lead_id, criteria_id)', 'Each criteria can only be scored once per lead!'),
    ]


class LeadAnalytics(models.Model):
    _name = 'lead.analytics'
    _description = 'Lead Analytics'
    _auto = False
    _order = 'date desc'

    date = fields.Date('Date')
    sales_rep_id = fields.Many2one('sales.rep', string='Sales Rep')
    source_id = fields.Many2one('lead.source', string='Source')
    stage_id = fields.Many2one('lead.stage', string='Stage')
    territory_id = fields.Many2one('territory.assignment', string='Territory')
    
    # Metrics
    lead_count = fields.Integer('Lead Count')
    qualified_count = fields.Integer('Qualified Count')
    converted_count = fields.Integer('Converted Count')
    lost_count = fields.Integer('Lost Count')
    
    total_revenue = fields.Float('Total Expected Revenue')
    avg_qualification_score = fields.Float('Avg Qualification Score')
    avg_days_to_convert = fields.Float('Avg Days to Convert')
    conversion_rate = fields.Float('Conversion Rate (%)')
    
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    row_number() OVER () AS id,
                    DATE(l.date_created) AS date,
                    l.sales_rep_id,
                    l.source_id,
                    l.stage_id,
                    ta.id AS territory_id,
                    COUNT(l.id) AS lead_count,
                    COUNT(CASE WHEN l.is_qualified THEN 1 END) AS qualified_count,
                    COUNT(CASE WHEN ls.is_won THEN 1 END) AS converted_count,
                    COUNT(CASE WHEN ls.is_lost THEN 1 END) AS lost_count,
                    SUM(l.expected_revenue) AS total_revenue,
                    AVG(l.qualification_score) AS avg_qualification_score,
                    AVG(CASE WHEN l.date_converted IS NOT NULL 
                        THEN EXTRACT(EPOCH FROM (l.date_converted - l.date_created))/86400 
                        END) AS avg_days_to_convert,
                    CASE WHEN COUNT(l.id) > 0 
                        THEN COUNT(CASE WHEN ls.is_won THEN 1 END) * 100.0 / COUNT(l.id) 
                        ELSE 0 END AS conversion_rate
                FROM sales_lead l
                LEFT JOIN lead_stage ls ON l.stage_id = ls.id
                LEFT JOIN sales_rep sr ON l.sales_rep_id = sr.id
                LEFT JOIN territory_assignment ta ON sr.id = ta.sales_rep_id
                GROUP BY DATE(l.date_created), l.sales_rep_id, l.source_id, l.stage_id, ta.id
            )
        """ % self._table)