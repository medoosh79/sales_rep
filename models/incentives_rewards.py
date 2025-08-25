# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class IncentiveProgram(models.Model):
    _name = 'incentive.program'
    _description = 'Incentive Program'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char('Program Name', required=True, tracking=True)
    code = fields.Char('Program Code', required=True, tracking=True)
    description = fields.Text('Description')
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True, tracking=True)
    
    # Program Configuration
    program_type = fields.Selection([
        ('sales_target', 'Sales Target'),
        ('customer_acquisition', 'Customer Acquisition'),
        ('product_focus', 'Product Focus'),
        ('territory_expansion', 'Territory Expansion'),
        ('customer_retention', 'Customer Retention'),
        ('training_completion', 'Training Completion'),
        ('performance_rating', 'Performance Rating')
    ], string='Program Type', required=True, tracking=True)
    
    calculation_method = fields.Selection([
        ('percentage', 'Percentage of Achievement'),
        ('fixed_amount', 'Fixed Amount'),
        ('tiered', 'Tiered Rewards'),
        ('points_based', 'Points Based')
    ], string='Calculation Method', required=True, default='percentage')
    
    # Period Configuration
    period_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom Period')
    ], string='Period Type', required=True, default='monthly')
    
    start_date = fields.Date('Start Date', required=True, tracking=True)
    end_date = fields.Date('End Date', required=True, tracking=True)
    
    # Target Configuration
    target_amount = fields.Float('Target Amount')
    target_quantity = fields.Integer('Target Quantity')
    target_percentage = fields.Float('Target Percentage')
    
    # Reward Configuration
    reward_type = fields.Selection([
        ('monetary', 'Monetary Reward'),
        ('points', 'Points'),
        ('gift', 'Gift/Prize'),
        ('recognition', 'Recognition'),
        ('time_off', 'Time Off')
    ], string='Reward Type', required=True, default='monetary')
    
    base_reward_amount = fields.Float('Base Reward Amount')
    max_reward_amount = fields.Float('Maximum Reward Amount')
    reward_currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # Eligibility
    eligible_sales_rep_ids = fields.Many2many(
        'sales.rep', 
        'incentive_program_sales_rep_rel', 
        'program_id', 
        'sales_rep_id',
        string='Eligible Sales Reps'
    )
    eligible_territory_ids = fields.Many2many(
        'sales.territory', 
        'incentive_program_territory_rel', 
        'program_id', 
        'territory_id',
        string='Eligible Territories'
    )
    min_employment_months = fields.Integer('Minimum Employment (Months)', default=0)
    
    # Program Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    # Statistics
    participant_count = fields.Integer('Participants', compute='_compute_statistics')
    total_rewards_paid = fields.Float('Total Rewards Paid', compute='_compute_statistics')
    achievement_rate = fields.Float('Achievement Rate (%)', compute='_compute_statistics')
    
    # Relations
    reward_tier_ids = fields.One2many('incentive.reward.tier', 'program_id', string='Reward Tiers')
    achievement_ids = fields.One2many('sales.rep.achievement', 'program_id', string='Achievements')
    
    @api.depends('achievement_ids')
    def _compute_statistics(self):
        for program in self:
            achievements = program.achievement_ids
            program.participant_count = len(achievements.mapped('sales_rep_id'))
            program.total_rewards_paid = sum(achievements.mapped('reward_amount'))
            
            if achievements:
                achieved_count = len(achievements.filtered('is_achieved'))
                program.achievement_rate = (achieved_count / len(achievements)) * 100
            else:
                program.achievement_rate = 0.0
    
    def action_activate(self):
        self.state = 'active'
        self._create_achievements()
    
    def action_pause(self):
        self.state = 'paused'
    
    def action_complete(self):
        self.state = 'completed'
        self._calculate_final_rewards()
    
    def action_cancel(self):
        self.state = 'cancelled'
    
    def action_view_participants(self):
        """View participants (achievements) for this program"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Program Participants',
            'res_model': 'sales.rep.achievement',
            'view_mode': 'tree,form',
            'domain': [('program_id', '=', self.id)],
            'context': {'default_program_id': self.id},
        }
    
    def action_view_total_rewards(self):
        """View total rewards for this program"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Program Rewards',
            'res_model': 'sales.rep.reward',
            'view_mode': 'tree,form',
            'domain': [('program_id', '=', self.id)],
            'context': {'default_program_id': self.id},
        }
    
    def action_view_achievement_rate(self):
        """View achievement rate details for this program"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Achievement Rate Details',
            'res_model': 'sales.rep.achievement',
            'view_mode': 'tree,form',
            'domain': [('program_id', '=', self.id)],
            'context': {'default_program_id': self.id, 'group_by': 'achievement_percentage'},
        }
    
    def _create_achievements(self):
        """Create achievement records for eligible sales reps"""
        eligible_reps = self._get_eligible_sales_reps()
        for rep in eligible_reps:
            self.env['sales.rep.achievement'].create({
                'program_id': self.id,
                'sales_rep_id': rep.id,
                'target_amount': self.target_amount,
                'target_quantity': self.target_quantity,
                'period_start': self.start_date,
                'period_end': self.end_date,
            })
    
    def _get_eligible_sales_reps(self):
        """Get sales reps eligible for this program"""
        domain = [('active', '=', True)]
        
        if self.eligible_sales_rep_ids:
            domain.append(('id', 'in', self.eligible_sales_rep_ids.ids))
        
        if self.eligible_territory_ids:
            domain.append(('territory_id', 'in', self.eligible_territory_ids.ids))
        
        if self.min_employment_months > 0:
            min_date = fields.Date.today() - relativedelta(months=self.min_employment_months)
            domain.append(('hire_date', '<=', min_date))
        
        return self.env['sales.representative'].search(domain)
    
    def _calculate_final_rewards(self):
        """Calculate final rewards for all achievements"""
        for achievement in self.achievement_ids:
            achievement._calculate_reward()


class IncentiveRewardTier(models.Model):
    _name = 'incentive.reward.tier'
    _description = 'Incentive Reward Tier'
    _order = 'program_id, min_achievement'
    
    program_id = fields.Many2one('incentive.program', string='Program', required=True, ondelete='cascade')
    name = fields.Char('Tier Name', required=True)
    min_achievement = fields.Float('Minimum Achievement (%)', required=True)
    max_achievement = fields.Float('Maximum Achievement (%)')
    reward_amount = fields.Float('Reward Amount')
    reward_percentage = fields.Float('Reward Percentage')
    bonus_points = fields.Integer('Bonus Points')
    description = fields.Text('Description')


class SalesRepAchievement(models.Model):
    _name = 'sales.rep.achievement'
    _description = 'Sales Rep Achievement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_start desc, sales_rep_id'
    
    name = fields.Char('Reference', required=True, copy=False, readonly=True, default=lambda self: 'New')
    program_id = fields.Many2one('incentive.program', string='Incentive Program', required=True, tracking=True)
    sales_rep_id = fields.Many2one('sales.rep', string='Sales Representative', required=True, tracking=True)
    
    # Period
    period_start = fields.Date('Period Start', required=True)
    period_end = fields.Date('Period End', required=True)
    
    # Targets
    target_amount = fields.Float('Target Amount')
    target_quantity = fields.Integer('Target Quantity')
    target_percentage = fields.Float('Target Percentage')
    
    # Actual Performance
    actual_amount = fields.Float('Actual Amount', compute='_compute_actual_performance', store=True)
    actual_quantity = fields.Integer('Actual Quantity', compute='_compute_actual_performance', store=True)
    actual_percentage = fields.Float('Actual Percentage', compute='_compute_actual_performance', store=True)
    
    # Achievement
    achievement_percentage = fields.Float('Achievement %', compute='_compute_achievement', store=True)
    is_achieved = fields.Boolean('Achieved', compute='_compute_achievement', store=True)
    
    # Rewards
    reward_amount = fields.Float('Reward Amount', tracking=True)
    reward_points = fields.Integer('Reward Points')
    reward_description = fields.Text('Reward Description')
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('achieved', 'Achieved'),
        ('not_achieved', 'Not Achieved'),
        ('rewarded', 'Rewarded')
    ], string='Status', default='draft', tracking=True)
    
    # Dates
    achievement_date = fields.Date('Achievement Date')
    reward_date = fields.Date('Reward Date')
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('sales.rep.achievement') or 'New'
        return super().create(vals)
    
    @api.depends('sales_rep_id', 'period_start', 'period_end', 'program_id')
    def _compute_actual_performance(self):
        for achievement in self:
            if not achievement.sales_rep_id or not achievement.period_start or not achievement.period_end:
                achievement.actual_amount = 0.0
                achievement.actual_quantity = 0
                achievement.actual_percentage = 0.0
                continue
            
            # Calculate based on program type
            if achievement.program_id.program_type == 'sales_target':
                achievement._compute_sales_performance()
            elif achievement.program_id.program_type == 'customer_acquisition':
                achievement._compute_customer_acquisition()
            elif achievement.program_id.program_type == 'training_completion':
                achievement._compute_training_completion()
            else:
                achievement.actual_amount = 0.0
                achievement.actual_quantity = 0
                achievement.actual_percentage = 0.0
    
    def _compute_sales_performance(self):
        """Compute sales performance for sales target programs"""
        # Get sales orders in the period
        orders = self.env['sale.order'].search([
            ('user_id', '=', self.sales_rep_id.user_id.id),
            ('date_order', '>=', self.period_start),
            ('date_order', '<=', self.period_end),
            ('state', 'in', ['sale', 'done'])
        ])
        
        self.actual_amount = sum(orders.mapped('amount_total'))
        self.actual_quantity = len(orders)
    
    def _compute_customer_acquisition(self):
        """Compute customer acquisition performance"""
        # Get new customers acquired in the period
        customers = self.env['res.partner'].search([
            ('create_date', '>=', self.period_start),
            ('create_date', '<=', self.period_end),
            ('is_company', '=', True),
            ('customer_rank', '>', 0)
        ])
        
        # Filter by sales rep's territory or assignments
        if self.sales_rep_id.territory_id:
            customers = customers.filtered(lambda c: c.state_id in self.sales_rep_id.territory_id.state_ids)
        
        self.actual_quantity = len(customers)
    
    def _compute_training_completion(self):
        """Compute training completion performance"""
        enrollments = self.env['training.enrollment'].search([
            ('sales_rep_id', '=', self.sales_rep_id.id),
            ('completion_date', '>=', self.period_start),
            ('completion_date', '<=', self.period_end),
            ('status', '=', 'completed'),
            ('passed', '=', True)
        ])
        
        self.actual_quantity = len(enrollments)
        if enrollments:
            self.actual_percentage = sum(enrollments.mapped('final_score')) / len(enrollments)
    
    @api.depends('target_amount', 'target_quantity', 'target_percentage', 'actual_amount', 'actual_quantity', 'actual_percentage')
    def _compute_achievement(self):
        for achievement in self:
            if achievement.target_amount > 0:
                achievement.achievement_percentage = (achievement.actual_amount / achievement.target_amount) * 100
            elif achievement.target_quantity > 0:
                achievement.achievement_percentage = (achievement.actual_quantity / achievement.target_quantity) * 100
            elif achievement.target_percentage > 0:
                achievement.achievement_percentage = (achievement.actual_percentage / achievement.target_percentage) * 100
            else:
                achievement.achievement_percentage = 0.0
            
            achievement.is_achieved = achievement.achievement_percentage >= 100.0
    
    def _calculate_reward(self):
        """Calculate reward based on achievement and program configuration"""
        if not self.is_achieved:
            self.reward_amount = 0.0
            self.reward_points = 0
            return
        
        program = self.program_id
        
        if program.calculation_method == 'fixed_amount':
            self.reward_amount = program.base_reward_amount
        elif program.calculation_method == 'percentage':
            base_amount = self.actual_amount if program.program_type == 'sales_target' else program.base_reward_amount
            self.reward_amount = base_amount * (program.base_reward_amount / 100)
        elif program.calculation_method == 'tiered':
            self._calculate_tiered_reward()
        elif program.calculation_method == 'points_based':
            self.reward_points = int(self.achievement_percentage * 10)
        
        # Apply maximum limit
        if program.max_reward_amount > 0 and self.reward_amount > program.max_reward_amount:
            self.reward_amount = program.max_reward_amount
    
    def _calculate_tiered_reward(self):
        """Calculate reward based on tier configuration"""
        tiers = self.program_id.reward_tier_ids.sorted('min_achievement')
        
        for tier in tiers:
            if (tier.min_achievement <= self.achievement_percentage and 
                (not tier.max_achievement or self.achievement_percentage <= tier.max_achievement)):
                
                if tier.reward_amount > 0:
                    self.reward_amount = tier.reward_amount
                elif tier.reward_percentage > 0:
                    base_amount = self.actual_amount if self.program_id.program_type == 'sales_target' else self.program_id.base_reward_amount
                    self.reward_amount = base_amount * (tier.reward_percentage / 100)
                
                self.reward_points = tier.bonus_points
                self.reward_description = tier.description
                break
    
    def action_mark_rewarded(self):
        """Mark achievement as rewarded"""
        self.state = 'rewarded'
        self.reward_date = fields.Date.today()


class SalesRepReward(models.Model):
    _name = 'sales.rep.reward'
    _description = 'Sales Rep Reward'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'reward_date desc, sales_rep_id'
    
    name = fields.Char('Reference', required=True, copy=False, readonly=True, default=lambda self: 'New')
    sales_rep_id = fields.Many2one('sales.rep', string='Sales Representative', required=True, tracking=True)
    achievement_id = fields.Many2one('sales.rep.achievement', string='Achievement', tracking=True)
    program_id = fields.Many2one('incentive.program', string='Program', related='achievement_id.program_id', store=True)
    
    # Reward Details
    reward_type = fields.Selection([
        ('monetary', 'Monetary Reward'),
        ('points', 'Points'),
        ('gift', 'Gift/Prize'),
        ('recognition', 'Recognition'),
        ('time_off', 'Time Off')
    ], string='Reward Type', required=True, tracking=True)
    
    reward_amount = fields.Float('Reward Amount', tracking=True)
    reward_points = fields.Integer('Reward Points')
    reward_description = fields.Text('Reward Description')
    
    # Dates
    reward_date = fields.Date('Reward Date', default=fields.Date.today, tracking=True)
    expiry_date = fields.Date('Expiry Date')
    
    # Status
    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='pending', tracking=True)
    
    # Payment
    payment_method = fields.Selection([
        ('salary', 'Add to Salary'),
        ('bonus', 'Separate Bonus'),
        ('gift_card', 'Gift Card'),
        ('bank_transfer', 'Bank Transfer')
    ], string='Payment Method')
    
    payment_date = fields.Date('Payment Date')
    payment_reference = fields.Char('Payment Reference')
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('sales.rep.reward') or 'New'
        return super().create(vals)
    
    def action_approve(self):
        self.state = 'approved'
    
    def action_pay(self):
        self.state = 'paid'
        self.payment_date = fields.Date.today()
    
    def action_cancel(self):
        self.state = 'cancelled'


class IncentiveAnalytics(models.Model):
    _name = 'incentive.analytics'
    _description = 'Incentive Analytics'
    _auto = False
    _rec_name = 'date'
    
    date = fields.Date('Date', readonly=True)
    sales_rep_id = fields.Many2one('sales.rep', string='Sales Rep', readonly=True)
    program_id = fields.Many2one('incentive.program', string='Program', readonly=True)
    territory_id = fields.Many2one('geo.node', string='Territory', readonly=True)
    
    # Metrics
    achievement_count = fields.Integer('Achievements', readonly=True)
    reward_count = fields.Integer('Rewards', readonly=True)
    total_reward_amount = fields.Float('Total Reward Amount', readonly=True)
    total_reward_points = fields.Integer('Total Reward Points', readonly=True)
    average_achievement_rate = fields.Float('Avg Achievement Rate (%)', readonly=True)
    
    # Performance
    target_amount = fields.Float('Target Amount', readonly=True)
    actual_amount = fields.Float('Actual Amount', readonly=True)
    achievement_percentage = fields.Float('Achievement %', readonly=True)
    
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    DATE(a.period_start) AS date,
                    a.sales_rep_id,
                    a.program_id,
                    ta.geo_node_id AS territory_id,
                    COUNT(a.id) AS achievement_count,
                    COUNT(r.id) AS reward_count,
                    COALESCE(SUM(r.reward_amount), 0) AS total_reward_amount,
                    COALESCE(SUM(r.reward_points), 0) AS total_reward_points,
                    AVG(a.achievement_percentage) AS average_achievement_rate,
                    AVG(a.target_amount) AS target_amount,
                    AVG(a.actual_amount) AS actual_amount,
                    AVG(a.achievement_percentage) AS achievement_percentage
                FROM sales_rep_achievement a
                LEFT JOIN sales_rep sr ON a.sales_rep_id = sr.id
                LEFT JOIN territory_assignment ta ON sr.id = ta.sales_rep_id AND ta.active = true
                LEFT JOIN sales_rep_reward r ON a.id = r.achievement_id
                GROUP BY
                    DATE(a.period_start),
                    a.sales_rep_id,
                    a.program_id,
                    ta.geo_node_id
            )
        """ % self._table)