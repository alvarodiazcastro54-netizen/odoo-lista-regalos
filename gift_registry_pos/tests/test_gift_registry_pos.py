from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import new_test_user, tagged

from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tagged("post_install", "-at_install")
class TestGiftRegistryPos(TestPoSCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        cls.product = cls.create_product("Cafetera", cls.categ_basic, 100.0)
        cls.owner = cls.env["res.partner"].create(
            {"name": "Ana Pérez", "vat": "12345678", "email": "ana@example.com"})
        cls.gift_list = cls.env["gift.registry"].create({
            "title": "Cumpleaños de Ana",
            "partner_id": cls.owner.id,
            "event_type_id": cls.env.ref("gift_registry.event_type_birthday").id,
            "event_date": fields.Date.add(fields.Date.today(), days=10),
            "consent_data": True,
            "line_ids": [(0, 0, {"product_id": cls.product.id, "qty_wanted": 2})],
        })
        cls.gift_list.action_activate()
        cls.reg_line = cls.gift_list.line_ids
        # Las pruebas de la caja usan una empresa propia: los avisos a administradores
        # solo van a quienes tienen acceso a la empresa de la lista
        company = cls.gift_list.company_id
        cls.manager = new_test_user(
            cls.env, login="lr_admin_caja",
            groups="base.group_user,gift_registry.group_gift_registry_manager",
            company_id=company.id, company_ids=[(6, 0, company.ids)])

    def _sell(self, qty=1, **line_values):
        order_data = self.create_ui_order_data([{
            "product": self.product, "quantity": qty,
            "gift_registry_line_id": self.reg_line.id,
            **line_values,
        }])
        result = self.env["pos.order"].sync_from_ui([order_data])
        return self.env["pos.order"].browse(result["pos.order"][0]["id"])

    def test_01_consent_required(self):
        with self.assertRaises(ValidationError):
            self.gift_list.copy({"consent_data": False}).write({"state": "active"})
        self.assertTrue(self.gift_list.consent_date)
        self.assertTrue(self.gift_list.name.startswith("LR-"))

    def test_02_sale_refund_and_exceeded(self):
        self.open_new_session()
        order = self._sell(1)
        self.assertEqual(order.state, "paid")
        self.assertEqual(self.reg_line.qty_gifted, 1)
        self.assertEqual(self.reg_line.qty_pending, 1)
        self.assertEqual(self.reg_line.status, "partial")
        self.assertEqual(self.gift_list.progress, 50)

        # Devolución desde el backend: hereda el enlace y resta
        refund_action = order.refund()
        refund = self.env["pos.order"].browse(refund_action["res_id"])
        self.assertEqual(refund.lines.gift_registry_line_id, self.reg_line)
        ctx = {"active_ids": refund.ids, "active_id": refund.id}
        payment = self.env["pos.make.payment"].with_context(**ctx).create(
            {"payment_method_id": self.cash_pm1.id})
        payment.with_context(**ctx).check()
        self.assertEqual(self.reg_line.qty_gifted, 0)
        self.assertEqual(self.reg_line.status, "pending")

        # Dos ventas de 2 unidades: se acepta el ticket y la línea queda excedida
        self._sell(2)
        self._sell(1)
        self.assertEqual(self.reg_line.qty_gifted, 3)
        self.assertEqual(self.reg_line.status, "exceeded")
        self.assertTrue(self.gift_list.has_exceeded_lines)

    def test_03_pos_loading_and_search(self):
        session = self.open_new_session()
        data = session.load_data([])
        self.assertIn(self.gift_list.id, [r["id"] for r in data["gift.registry"]])
        self.assertIn(self.reg_line.id, [r["id"] for r in data["gift.registry.line"]])
        self.assertNotIn("partner_id", data["gift.registry"][0])

        Registry = self.env["gift.registry"]
        by_dni = Registry.search_for_pos("12345678", self.config.id)
        by_code = Registry.search_for_pos(self.gift_list.name, self.config.id)
        by_name = Registry.search_for_pos("Ana", self.config.id)
        for result in (by_dni, by_code, by_name):
            self.assertEqual([r["id"] for r in result["gift.registry"]], [self.gift_list.id])
        # Una lista privada no aparece por nombre, sí por DNI
        self.gift_list.privacy = "code"
        self.assertFalse(Registry.search_for_pos("Ana", self.config.id)["gift.registry"])
        self.assertTrue(Registry.search_for_pos("12345678", self.config.id)["gift.registry"])
        # El DNI parcial no encuentra nada
        self.assertFalse(Registry.search_for_pos("123456", self.config.id)["gift.registry"])

    def test_04_event_today_notice_after_sales(self):
        """El aviso diario refleja lo vendido en caja."""
        self.gift_list.event_date = fields.Date.context_today(
            self.gift_list.with_context(tz="America/Lima"))
        prefix = f"Hoy: Cumpleaños de Ana · {self.gift_list.name} · "
        self.open_new_session()
        self._sell(1)
        self.assertEqual(
            self.gift_list._get_event_today_summary(),
            prefix + "1 de 2 regalos cubiertos (50 %)")

        self._sell(1)
        with self.enter_registry_test_mode():
            self.env.ref("gift_registry.ir_cron_gift_registry_event_today").method_direct_trigger()
        notices = self.env["mail.activity"].search([
            ("res_model", "=", "gift.registry"), ("res_id", "=", self.gift_list.id)])
        self.assertTrue(notices)
        self.assertEqual(set(notices.mapped("summary")), {prefix + "Lista completa"})

    def _exceeded_notices(self):
        return self.env["mail.activity"].search([
            ("res_model", "=", "gift.registry"), ("res_id", "=", self.gift_list.id),
            ("summary", "like", "Regalo excedido"),
        ])

    def test_05_exceeded_notice_for_managers(self):
        """Al superar lo deseado se avisa una sola vez a cada administrador."""
        managers = self.gift_list._get_manager_users()
        self.assertIn(self.manager, managers)
        self.open_new_session()

        self._sell(2)
        self.assertEqual(self.reg_line.status, "done")
        self.assertFalse(self._exceeded_notices(), "Completar la lista no es un exceso")

        third_order = self._sell(1)
        self.assertEqual(self.reg_line.status, "exceeded")
        notices = self._exceeded_notices()
        self.assertEqual(len(notices), len(managers))
        self.assertEqual(notices.user_id, managers)
        self.assertEqual(
            notices[0].summary,
            f"Regalo excedido: {self.product.display_name} · {self.gift_list.name} · 3 de 2")

        fourth_order = self._sell(1)
        self.assertEqual(len(self._exceeded_notices()), len(managers), "No se duplica")

        # Devolver los dos pedidos de más deja la línea completa: si se vuelve a
        # exceder, se avisa de nuevo
        for order in (third_order, fourth_order):
            refund = self.env["pos.order"].browse(order.refund()["res_id"])
            ctx = {"active_ids": refund.ids, "active_id": refund.id}
            self.env["pos.make.payment"].with_context(**ctx).create(
                {"payment_method_id": self.cash_pm1.id}).with_context(**ctx).check()
        self.assertEqual(self.reg_line.status, "done")
        self.assertFalse(self.reg_line.exceeded_notified)
        self._exceeded_notices().unlink()
        self._sell(1)
        self.assertEqual(len(self._exceeded_notices()), len(managers))

    def test_06_guest_dedication(self):
        """La dedicatoria del invitado viaja con la venta y queda en la lista."""
        self.assertIn(
            "gift_message", self.env["pos.order.line"]._load_pos_data_fields(self.config))
        self.open_new_session()
        order = self._sell(1, gift_message="Con cariño, de la tía Rosa")
        self.assertEqual(order.lines.gift_message, "Con cariño, de la tía Rosa")
        self.assertEqual(self.gift_list.pos_line_ids.gift_message, "Con cariño, de la tía Rosa")

        # Sin dedicatoria el campo queda vacío; una demasiado larga se recorta a 120
        self.assertFalse(self._sell(1).lines.gift_message)
        self.assertEqual(len(self._sell(1, gift_message="x" * 300).lines.gift_message), 120)
