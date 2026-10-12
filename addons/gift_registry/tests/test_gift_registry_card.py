import base64

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestGiftRegistryCard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # La base de pruebas se crea sin español: se activa para comprobar la fecha en palabras
        cls.env["res.lang"]._activate_lang("es_PE")
        owner = cls.env["res.partner"].create({"name": "Lucía Ramos"})
        product = cls.env["product.product"].create({"name": "Cuna"})
        cls.gift_list = cls.env["gift.registry"].with_context(lang="es_PE").create({
            "title": "Baby shower de Lucía",
            "partner_id": owner.id,
            "event_type_id": cls.env.ref("gift_registry.event_type_baby_shower").id,
            "event_date": fields.Date.to_date("2026-10-17"),
            "message": "Gracias por acompañarnos",
            "consent_data": True,
            "line_ids": [(0, 0, {"product_id": product.id, "qty_wanted": 1})],
        })

    def test_card_shows_list_data_and_qr(self):
        html = self.env["ir.actions.report"].with_context(lang="es_PE")._render_qweb_html(
            "gift_registry.report_gift_registry_card", self.gift_list.ids)[0].decode()
        for expected in ("Baby shower de Lucía", "Lucía Ramos", self.gift_list.name,
                         "Gracias por acompañarnos", "LISTA DE REGALOS"):
            self.assertIn(expected, html)
        # El QR va incrustado en la página, no como dirección web
        self.assertIn('src="data:image/png;base64,', html)
        self.assertNotIn("/report/barcode", html)

    def test_qr_is_a_png_with_the_list_code(self):
        png = base64.b64decode(self.gift_list._get_card_qr())
        self.assertTrue(png.startswith(b"\x89PNG\r\n"))
        # El mismo código produce siempre el mismo QR; otro código, uno distinto
        other = self.gift_list.copy()
        self.assertEqual(self.gift_list._get_card_qr(), self.gift_list._get_card_qr())
        self.assertNotEqual(self.gift_list._get_card_qr(), other._get_card_qr())

    def test_event_date_in_words(self):
        label = self.gift_list.with_context(lang="es_PE")._get_event_date_label()
        self.assertEqual(label, "sábado, 17 de octubre de 2026")
