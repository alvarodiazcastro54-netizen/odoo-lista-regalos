from odoo import api, fields, models
from odoo.tools import float_compare


class GiftRegistryLine(models.Model):
    _name = "gift.registry.line"
    _description = "Producto de una lista de regalos"
    _order = "registry_id, sequence, id"
    _check_company_auto = True

    registry_id = fields.Many2one(
        "gift.registry", "Lista", required=True, ondelete="cascade", index=True,
    )
    company_id = fields.Many2one(related="registry_id.company_id", store=True, index=True)
    registry_state = fields.Selection(related="registry_id.state", store=True, index=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        "product.product", "Producto", required=True, index=True,
        domain=[("sale_ok", "=", True)], check_company=True,
    )
    product_tmpl_id = fields.Many2one(related="product_id.product_tmpl_id", store=True)
    product_uom_id = fields.Many2one(related="product_id.uom_id")
    qty_wanted = fields.Float("Cantidad deseada", default=1.0, required=True, digits="Product Unit")
    qty_gifted = fields.Float(
        "Cantidad regalada", compute="_compute_qty_gifted", store=True, digits="Product Unit",
    )
    qty_pending = fields.Float(
        "Pendiente", compute="_compute_qty_gifted", store=True, digits="Product Unit",
    )
    status = fields.Selection(
        [("pending", "Pendiente"), ("partial", "Parcial"),
         ("done", "Completo"), ("exceeded", "Excedido")],
        compute="_compute_qty_gifted", store=True, index=True,
    )
    qty_available = fields.Float(
        "Stock disponible", compute="_compute_qty_available", digits="Product Unit",
    )
    priority = fields.Selection(
        [("0", "Normal"), ("1", "Importante"), ("2", "Muy deseado")], default="0",
    )
    note = fields.Char("Nota para el invitado")
    accept_other_variant = fields.Boolean("Acepta otra variante")

    _qty_wanted_positive = models.Constraint(
        "CHECK(qty_wanted > 0)", "La cantidad deseada debe ser mayor que cero.",
    )
    _product_registry_uniq = models.Constraint(
        "UNIQUE(registry_id, product_id)",
        "El producto ya está en esta lista; aumente su cantidad.",
    )

    def _get_gifted_qty(self):
        """Suma de lo regalado por todos los canales.

        El núcleo devuelve 0; gift_registry_pos y gift_registry_sale
        extienden este método y agregan sus dependencias.
        """
        self.ensure_one()
        return 0.0

    @api.depends("qty_wanted")
    def _compute_qty_gifted(self):
        for line in self:
            gifted = line._get_gifted_qty()
            rounding = line.product_uom_id.rounding or 0.01
            line.qty_gifted = gifted
            line.qty_pending = max(line.qty_wanted - gifted, 0.0)
            cmp = float_compare(gifted, line.qty_wanted, precision_rounding=rounding)
            line.status = ("exceeded" if cmp > 0 else "done" if cmp == 0
                           else "partial" if gifted > 0 else "pending")

    @api.depends_context("warehouse_id")
    @api.depends("product_id")
    def _compute_qty_available(self):
        # Con el contexto warehouse_id (lo envía el POS) muestra el stock de ese almacén
        for line in self:
            line.qty_available = line.product_id.qty_available
