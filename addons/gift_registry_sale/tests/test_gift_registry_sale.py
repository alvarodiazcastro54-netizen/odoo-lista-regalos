from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestGiftRegistrySale(TransactionCase):

    def test_confirm_and_cancel(self):
        product = self.env["product.product"].create(
            {"name": "Peluche", "type": "consu", "is_storable": True, "list_price": 50})
        owner = self.env["res.partner"].create({"name": "Luis", "email": "luis@example.com"})
        guest = self.env["res.partner"].create({"name": "Invitada"})
        registry = self.env["gift.registry"].create({
            "title": "Baby shower",
            "partner_id": owner.id,
            "event_type_id": self.env.ref("gift_registry.event_type_baby_shower").id,
            "event_date": fields.Date.today(),
            "consent_data": True,
            "line_ids": [(0, 0, {"product_id": product.id, "qty_wanted": 1})],
        })
        line = registry.line_ids
        order = self.env["sale.order"].create({
            "partner_id": guest.id,
            "order_line": [(0, 0, {"product_id": product.id, "product_uom_qty": 1,
                                   "gift_registry_line_id": line.id})],
        })
        self.assertEqual(line.qty_gifted, 0, "Una cotización no cuenta")
        mails_before = self.env["mail.mail"].search_count([])
        order.action_confirm()
        self.assertEqual(line.qty_gifted, 1)
        self.assertGreater(self.env["mail.mail"].search_count([]), mails_before,
                           "Se encola el aviso al dueño")
        self.assertEqual(line.status, "done")
        order._action_cancel()
        self.assertEqual(line.qty_gifted, 0, "Un pedido cancelado deja de contar")

    def test_exceeded_notice_for_managers(self):
        """Un pedido de venta que supera lo deseado avisa una vez a los administradores."""
        product = self.env["product.product"].create(
            {"name": "Peluche", "type": "consu", "is_storable": True, "list_price": 50})
        owner = self.env["res.partner"].create({"name": "Luis", "email": "luis@example.com"})
        guest = self.env["res.partner"].create({"name": "Invitada"})
        registry = self.env["gift.registry"].create({
            "title": "Baby shower",
            "partner_id": owner.id,
            "event_type_id": self.env.ref("gift_registry.event_type_baby_shower").id,
            "event_date": fields.Date.today(),
            "consent_data": True,
            "line_ids": [(0, 0, {"product_id": product.id, "qty_wanted": 1})],
        })
        line = registry.line_ids
        managers = registry._get_manager_users()
        self.assertTrue(managers)

        def sell(qty):
            self.env["sale.order"].create({
                "partner_id": guest.id,
                "order_line": [(0, 0, {"product_id": product.id, "product_uom_qty": qty,
                                       "gift_registry_line_id": line.id})],
            }).action_confirm()

        def notices():
            return self.env["mail.activity"].search([
                ("res_model", "=", "gift.registry"), ("res_id", "=", registry.id),
                ("summary", "like", "Regalo excedido"),
            ])

        sell(2)
        self.assertEqual(line.status, "exceeded")
        self.assertEqual(notices().user_id, managers)
        self.assertEqual(len(notices()), len(managers))
        sell(1)
        self.assertEqual(len(notices()), len(managers), "No se duplica")
