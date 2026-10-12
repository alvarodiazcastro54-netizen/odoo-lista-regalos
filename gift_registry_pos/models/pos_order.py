from odoo import api, fields, models


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    gift_registry_line_id = fields.Many2one(
        "gift.registry.line", "Línea de lista de regalos",
        index="btree_not_null", ondelete="restrict", copy=False,
    )
    gift_registry_id = fields.Many2one(
        related="gift_registry_line_id.registry_id", store=True, index="btree_not_null",
    )
    # Texto libre del invitado; se imprime bajo la leyenda "Regalo para ..."
    gift_message = fields.Char("Dedicatoria del invitado", size=120, copy=False)

    @api.model
    def _load_pos_data_fields(self, config):
        # Sin esto los campos no viajan entre la caja y el servidor
        return super()._load_pos_data_fields(config) + ["gift_registry_line_id", "gift_message"]

    @api.model_create_multi
    def create(self, vals_list):
        # Una devolución hereda el enlace de la línea original y resta la cantidad
        for vals in vals_list:
            if vals.get("refunded_orderline_id") and not vals.get("gift_registry_line_id"):
                origin = self.browse(vals["refunded_orderline_id"])
                if origin.gift_registry_line_id:
                    vals["gift_registry_line_id"] = origin.gift_registry_line_id.id
        return super().create(vals_list)


class PosOrder(models.Model):
    _inherit = "pos.order"

    def action_pos_order_paid(self):
        res = super().action_pos_order_paid()
        self._gift_registry_notify()
        # Si algún regalo superó lo deseado, aviso a los administradores (una vez por línea)
        self.lines.gift_registry_line_id.sudo()._notify_exceeded()
        return res

    def _gift_registry_notify(self):
        """Programa el aviso al dueño. send_mail() sin force_send usa la cola,
        así la sincronización de la caja no espera al servidor de correo."""
        template = self.env.ref("gift_registry.mail_template_gift_received",
                                raise_if_not_found=False)
        for line in self.lines.filtered(lambda l: l.gift_registry_line_id and l.qty > 0):
            template and template.send_mail(line.gift_registry_line_id.id)
