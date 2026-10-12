import base64
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools import float_compare, float_round, format_date

_logger = logging.getLogger(__name__)

CONSENT_TEXT_VERSION = "2026-10"


def _format_qty(qty):
    """3.0 -> "3"; 2.5 -> "2.5" (las cantidades casi siempre son enteras)."""
    return f"{qty:.2f}".rstrip("0").rstrip(".")


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
        "res.users", "Responsable", default=lambda self: self.env.user,
    )
    # Día en que se creó el aviso "evento hoy": evita duplicarlo si la tarea corre otra vez
    event_notice_date = fields.Date("Aviso de evento creado el", readonly=True, copy=False)
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

    @api.onchange("event_type_id")
    def _onchange_event_type_id(self):
        """Propone los productos sugeridos del tipo de evento en una lista aún sin productos."""
        suggested = self.event_type_id.template_line_ids
        if self.line_ids or not suggested:
            return
        self.line_ids = [
            Command.create({"product_id": product.id, "qty_wanted": 1.0})
            for product in suggested
        ]

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

    # --- Tarjeta imprimible ---------------------------------------------------
    def _get_event_date_label(self):
        """Fecha del evento en palabras: "sábado, 17 de octubre de 2026"."""
        self.ensure_one()
        return format_date(self.env, self.event_date, date_format="EEEE, d 'de' MMMM 'de' y")

    def _get_card_qr(self):
        """QR (PNG en base64) con el código de la lista.

        Se incrusta en el reporte: así el PDF no necesita pedir la imagen al servidor.
        """
        self.ensure_one()
        png = self.env["ir.actions.report"].barcode("QR", self.name, width=300, height=300)
        return base64.b64encode(png)

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

    # --- Aviso diario de eventos ----------------------------------------------
    def _get_event_today_summary(self):
        """Texto del aviso: "Hoy: Baby shower de Ana · LR-00012 · 3 de 5 regalos cubiertos (60 %)".

        Lo cubierto se cuenta por producto y sin pasar de lo deseado: un producto
        regalado de más no compensa a otro que sigue pendiente.
        """
        self.ensure_one()
        wanted = sum(self.line_ids.mapped("qty_wanted"))
        covered = sum(
            max(min(line.qty_gifted, line.qty_wanted), 0.0) for line in self.line_ids
        )
        if not wanted:
            status = _("sin productos")
        elif float_compare(covered, wanted, precision_digits=2) >= 0:
            status = _("Lista completa")
        else:
            # Tope de 99: mientras falte algo no debe leerse "100 %"
            percent = min(int(float_round(covered / wanted * 100, precision_digits=0)), 99)
            status = _(
                "%(covered)s de %(wanted)s regalos cubiertos (%(percent)s %%)",
                covered=_format_qty(covered), wanted=_format_qty(wanted), percent=percent,
            )
        return _(
            "Hoy: %(title)s · %(code)s · %(status)s",
            title=self.title, code=self.name, status=status,
        )

    def _get_manager_users(self):
        """Administradores de listas de regalos activos y con acceso a la empresa de la lista."""
        self.ensure_one()
        # sudo: quien dispara un aviso (un cajero, un pedido web) puede no poder leer los grupos
        managers = self.env.ref("gift_registry.group_gift_registry_manager").sudo().all_user_ids
        return managers.filtered(
            lambda user: user.active and not user.share and self.company_id in user.company_ids
        )

    def _get_event_notice_users(self):
        """El responsable de la lista; si no tiene (o está archivado), los administradores."""
        self.ensure_one()
        return self.user_id if self.user_id.active else self._get_manager_users()

    @api.model
    def _cron_event_today_activity(self):
        """Crea una actividad "Por hacer" por cada lista activa cuyo evento es hoy.

        "Hoy" sale de la zona horaria del contexto (la tarea programada envía la
        de Perú). Sin ella Odoo usaría UTC, que desde las 7 p. m. de Lima ya es
        el día siguiente.
        """
        today = fields.Date.context_today(self)
        registries = self.search([("state", "=", "active"), ("event_date", "=", today)])
        for registry in registries.filtered(lambda r: r.event_notice_date != today):
            users = registry._get_event_notice_users()
            if not users:
                _logger.warning(
                    "Lista %s: sin responsable ni administradores a quien avisar", registry.name)
                continue
            summary = registry._get_event_today_summary()
            for user in users:
                registry.activity_schedule(
                    "mail.mail_activity_data_todo", date_deadline=today,
                    summary=summary, user_id=user.id,
                )
            registry.event_notice_date = today
