from datetime import timedelta

from odoo import api, fields, models
from odoo.fields import Domain

COUNTED_POS_STATES = ("paid", "done")


class GiftRegistry(models.Model):
    _name = "gift.registry"
    _inherit = ["gift.registry", "pos.load.mixin"]

    pos_line_ids = fields.One2many("pos.order.line", "gift_registry_id", "Ventas en caja")

    # --- Carga inicial en la sesión del POS (para trabajar sin conexión) ---
    @api.model
    def _load_pos_data_domain(self, data, config):
        today = fields.Date.context_today(self)
        return [
            ("state", "=", "active"),
            ("company_id", "=", config.company_id.id),
            ("event_date", ">=", today - timedelta(days=config.gift_registry_days_before)),
            ("event_date", "<=", today + timedelta(days=config.gift_registry_days_after)),
        ]

    @api.model
    def _load_pos_data_fields(self, config):
        # Sin DNI ni fecha de nacimiento: la caja solo necesita identificar la lista
        # Campos relacionados de texto: la caja no carga todos los contactos
        return ["id", "name", "title", "partner_name", "event_type_name", "event_date",
                "privacy", "message", "line_ids", "write_date"]

    # --- Búsqueda en línea desde la caja ------------------------------------
    @api.model
    def search_for_pos(self, query, config_id, limit=20):
        config = self.env["pos.config"].browse(config_id)
        query = (query or "").strip()
        if len(query) < 3:
            return {}
        base = Domain([("state", "=", "active"), ("company_id", "=", config.company_id.id)])
        by_code_or_dni = Domain.OR([
            [("name", "=ilike", query)],
            [("partner_id.vat", "=", query)],  # coincidencia exacta del DNI
        ])
        by_name = Domain([("privacy", "=", "public")]) & Domain.OR([
            [("partner_id.name", "ilike", query)],
            [("title", "ilike", query)],
        ])
        registries = self.search(base & (by_code_or_dni | by_name), limit=limit)
        lines = registries.line_ids.with_context(warehouse_id=config.warehouse_id.id)
        # callRelated() en la caja conecta estos datos con sus modelos locales
        return {
            "gift.registry": self._load_pos_data_read(registries, config),
            "gift.registry.line": lines._load_pos_data_read(lines, config),
        }


class GiftRegistryLine(models.Model):
    _name = "gift.registry.line"
    _inherit = ["gift.registry.line", "pos.load.mixin"]

    pos_line_ids = fields.One2many("pos.order.line", "gift_registry_line_id", "Ventas en caja")

    @api.depends("pos_line_ids.qty", "pos_line_ids.order_id.state")
    def _compute_qty_gifted(self):
        return super()._compute_qty_gifted()

    def _get_gifted_qty(self):
        qty = super()._get_gifted_qty()
        # Las devoluciones tienen cantidad negativa y se restan solas
        return qty + sum(
            self.pos_line_ids.filtered(
                lambda l: l.order_id.state in COUNTED_POS_STATES).mapped("qty")
        )

    @api.model
    def _load_pos_data_domain(self, data, config):
        registry_ids = [r["id"] for r in data.get("gift.registry", [])]
        return [("registry_id", "in", registry_ids)]

    @api.model
    def _load_pos_data_fields(self, config):
        return ["id", "registry_id", "product_id", "qty_wanted", "qty_gifted",
                "qty_pending", "status", "qty_available", "note",
                "accept_other_variant", "priority", "write_date"]

    @api.model
    def get_status_for_pos(self, line_ids, config_id):
        """Revalida en línea justo antes de agregar al ticket."""
        config = self.env["pos.config"].browse(config_id)
        lines = self.browse(line_ids).with_context(warehouse_id=config.warehouse_id.id)
        return {"gift.registry.line": self._load_pos_data_read(lines, config)}


class PosSession(models.Model):
    _inherit = "pos.session"

    @api.model
    def _load_pos_data_models(self, config):
        models_to_load = super()._load_pos_data_models(config)
        if config.gift_registry_enabled:
            # El orden importa: las líneas se filtran con las listas ya cargadas
            models_to_load += ["gift.registry", "gift.registry.line"]
        return models_to_load


class PosConfig(models.Model):
    _inherit = "pos.config"

    gift_registry_enabled = fields.Boolean("Listas de regalos", default=True)
    gift_registry_days_before = fields.Integer("Cargar eventos desde (días atrás)", default=30)
    gift_registry_days_after = fields.Integer("Cargar eventos hasta (días adelante)", default=90)
