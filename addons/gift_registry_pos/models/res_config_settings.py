from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_gift_registry_enabled = fields.Boolean(
        related="pos_config_id.gift_registry_enabled", readonly=False)
    pos_gift_registry_days_before = fields.Integer(
        related="pos_config_id.gift_registry_days_before", readonly=False)
    pos_gift_registry_days_after = fields.Integer(
        related="pos_config_id.gift_registry_days_after", readonly=False)
