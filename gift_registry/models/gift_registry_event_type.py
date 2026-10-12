from odoo import fields, models


class GiftRegistryEventType(models.Model):
    _name = "gift.registry.event.type"
    _description = "Tipo de evento de lista de regalos"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    template_line_ids = fields.Many2many(
        "product.product", string="Productos sugeridos",
        help="Se copian al crear una lista de este tipo.",
    )
