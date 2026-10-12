from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

CONSENT_TEXT_VERSION = "2026-10"


class GiftRegistry(models.Model):
    _name = "gift.registry"
    _description = "Lista de regalos"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "event_date desc, id desc"
    _rec_names_search = ["name", "title", "partner_id.name"]
    _check_company_auto = True

    name = fields.Char(
        "Código", required=True, copy=False, readonly=True, index="trigram",
        default=lambda self: _("Nuevo"),
    )
    title = fields.Char("Título", required=True, tracking=True)
    partner_id = fields.Many2one(
        "res.partner", "Dueño de la lista", required=True, index=True,
        tracking=True, check_company=True,
    )
    partner_name = fields.Char(related="partner_id.name", string="Nombre del dueño")
    event_type_id = fields.Many2one(
        "gift.registry.event.type", "Tipo de evento", required=True,
    )
    event_type_name = fields.Char(related="event_type_id.name", string="Evento")
    event_date = fields.Date("Fecha del evento", required=True, index=True, tracking=True)
    close_date = fields.Date(
        "Fecha de cierre", compute="_compute_close_date", store=True,
        readonly=False, index=True,
    )
    state = fields.Selection(
        [("draft", "Borrador"), ("active", "Activa"),
         ("closed", "Cerrada"), ("cancel", "Cancelada")],
        default="draft", required=True, index=True, tracking=True, copy=False,
    )
    privacy = fields.Selection(
        [("public", "Pública (se busca por nombre)"),
         ("code", "Privada (solo por código o DNI)")],
        default="public", required=True,
    )
    message = fields.Text("Mensaje para los invitados")
    delivery_mode = fields.Selection(
        [("giver", "El invitado se lleva el regalo"),
         ("store", "Queda en tienda para el dueño")],
        default="giver", required=True,
    )
    user_id = fields.Many2one(
        "res.users", "Vendedor responsable", default=lambda self: self.env.user,
    )
    company_id = fields.Many2one(
        "res.company", required=True, index=True,
        default=lambda self: self.env.company,
    )
    line_ids = fields.One2many("gift.registry.line", "registry_id", "Productos", copy=True)

    # Consentimiento (Ley N.º 29733)
    consent_data = fields.Boolean("Acepta el tratamiento de sus datos", copy=False, tracking=True)
    consent_marketing = fields.Boolean("Acepta recibir publicidad", copy=False, tracking=True)
    consent_date = fields.Datetime(readonly=True, copy=False)
    consent_user_id = fields.Many2one("res.users", readonly=True, copy=False)
    consent_text_version = fields.Char(readonly=True, copy=False)

    # Totales
    qty_wanted_total = fields.Float(compute="_compute_totals", store=True)
    qty_gifted_total = fields.Float(compute="_compute_totals", store=True)
    progress = fields.Float("Avance (%)", compute="_compute_totals", store=True, aggregator="avg")
    has_exceeded_lines = fields.Boolean(compute="_compute_totals", store=True)

    _name_company_uniq = models.Constraint(
        "UNIQUE(name, company_id)",
        "El código de la lista debe ser único por empresa.",
    )

    @api.depends("event_date")
    def _compute_close_date(self):
        days = int(self.env["ir.config_parameter"].sudo().get_param(
            "gift_registry.close_after_days", 15))
        for registry in self:
            registry.close_date = (
                registry.event_date + timedelta(days=days) if registry.event_date else False
            )

    @api.depends("line_ids.qty_wanted", "line_ids.qty_gifted")
    def _compute_totals(self):
        for registry in self:
            wanted = sum(registry.line_ids.mapped("qty_wanted"))
            gifted = sum(registry.line_ids.mapped("qty_gifted"))
            registry.qty_wanted_total = wanted
            registry.qty_gifted_total = gifted
            registry.progress = min(gifted / wanted, 1.0) * 100 if wanted else 0.0
            registry.has_exceeded_lines = any(
                line.status == "exceeded" for line in registry.line_ids
            )

    @api.constrains("state", "consent_data")
    def _check_consent(self):
        for registry in self:
            if registry.state == "active" and not registry.consent_data:
                raise ValidationError(_(
                    "La lista %s no puede activarse sin el consentimiento del titular.",
                    registry.name,
                ))

    @api.model
    def _consent_vals(self):
        return {
            "consent_date": fields.Datetime.now(),
            "consent_user_id": self.env.uid,
            "consent_text_version": CONSENT_TEXT_VERSION,
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
                vals["name"] = self.env["ir.sequence"].with_company(company).next_by_code(
                    "gift.registry") or _("Nuevo")
            if vals.get("consent_data"):
                vals.update(self._consent_vals())
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("consent_data"):
            vals = {**vals, **self._consent_vals()}
        return super().write(vals)

    # --- Acciones de estado -------------------------------------------------
    def action_activate(self):
        for registry in self:
            if not registry.line_ids:
                raise UserError(_("Agregue al menos un producto antes de activar la lista."))
        self.write({"state": "active"})
        template = self.env.ref("gift_registry.mail_template_registry_activated")
        for registry in self:
            template.send_mail(registry.id)  # cola de correo, no bloquea

    def action_close(self):
        self.write({"state": "closed"})

    def action_cancel(self):
        self.write({"state": "cancel"})

    def action_draft(self):
        self.write({"state": "draft"})

    # --- Tareas programadas -------------------------------------------------
    @api.model
    def _cron_close_expired(self):
        expired = self.search([
            ("state", "=", "active"),
            ("close_date", "<", fields.Date.context_today(self)),
        ])
        expired.action_close()

    @api.model
    def _cron_event_reminder(self, days_before=7):
        target = fields.Date.context_today(self) + timedelta(days=days_before)
        template = self.env.ref("gift_registry.mail_template_registry_reminder")
        for registry in self.search([("state", "=", "active"), ("event_date", "=", target)]):
            template.send_mail(registry.id)
