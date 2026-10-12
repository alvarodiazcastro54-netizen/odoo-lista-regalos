from odoo import fields, models, tools


class GiftRegistryReport(models.Model):
    _name = "gift.registry.report"
    _description = "Análisis de listas de regalos"
    _auto = False
    _order = "event_date desc"

    registry_id = fields.Many2one("gift.registry", readonly=True)
    partner_id = fields.Many2one("res.partner", readonly=True)
    event_type_id = fields.Many2one("gift.registry.event.type", readonly=True)
    event_date = fields.Date(readonly=True)
    state = fields.Selection(
        [("draft", "Borrador"), ("active", "Activa"),
         ("closed", "Cerrada"), ("cancel", "Cancelada")], readonly=True)
    product_id = fields.Many2one("product.product", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    qty_wanted = fields.Float(readonly=True)
    qty_gifted = fields.Float(readonly=True)
    is_gifted = fields.Integer("Líneas con regalo", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT l.id, r.id AS registry_id, r.partner_id, r.event_type_id,
                       r.event_date, r.state, r.company_id, l.product_id,
                       l.qty_wanted, l.qty_gifted,
                       CASE WHEN l.qty_gifted > 0 THEN 1 ELSE 0 END AS is_gifted
                  FROM gift_registry_line l
                  JOIN gift_registry r ON r.id = l.registry_id
            )
        """)
