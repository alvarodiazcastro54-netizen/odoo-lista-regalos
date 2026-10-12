from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    gift_registry_line_id = fields.Many2one(
        "gift.registry.line", "Línea de lista de regalos",
        index="btree_not_null", ondelete="restrict", copy=False,
    )


class GiftRegistryLine(models.Model):
    _inherit = "gift.registry.line"

    sale_line_ids = fields.One2many("sale.order.line", "gift_registry_line_id", "Ventas web")

    @api.depends(
        "sale_line_ids.product_uom_qty",
        "sale_line_ids.state",
        "sale_line_ids.move_ids.state",
        "sale_line_ids.move_ids.quantity",
    )
    def _compute_qty_gifted(self):
        return super()._compute_qty_gifted()

    def _get_gifted_qty(self):
        qty = super()._get_gifted_qty()
        for sol in self.sale_line_ids.filtered(lambda l: l.state == "sale"):
            # Devoluciones validadas en almacén: movimientos de entrada de cliente
            returned = sum(
                sol.move_ids.filtered(
                    lambda m: m.state == "done" and m.origin_returned_move_id
                ).mapped("quantity")
            )
            qty += sol.product_uom_qty - returned
        # Un pedido cancelado tiene state 'cancel' y deja de contar solo
        return qty


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        res = super()._action_confirm()
        template = self.env.ref("gift_registry.mail_template_gift_received",
                                raise_if_not_found=False)
        for line in self.order_line.filtered("gift_registry_line_id"):
            template and template.send_mail(line.gift_registry_line_id.id)
        return res
