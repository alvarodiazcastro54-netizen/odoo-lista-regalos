from odoo import fields
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEventTypeTemplate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner = cls.env["res.partner"].create({"name": "Ana Pérez"})
        cls.crib, cls.stroller, cls.toaster = cls.env["product.product"].create(
            [{"name": "Cuna"}, {"name": "Coche de bebé"}, {"name": "Tostadora"}])
        cls.baby_shower = cls.env.ref("gift_registry.event_type_baby_shower")
        cls.baby_shower.template_line_ids = cls.crib | cls.stroller
        cls.wedding = cls.env.ref("gift_registry.event_type_wedding")
        cls.wedding.template_line_ids = cls.toaster
        cls.birthday = cls.env.ref("gift_registry.event_type_birthday")
        cls.birthday.template_line_ids = False

    def _new_list_form(self, event_type):
        """Formulario de lista nueva, como lo llenaría un usuario en pantalla."""
        form = Form(self.env["gift.registry"])
        form.title = "Lista de prueba"
        form.partner_id = self.owner
        form.event_date = fields.Date.today()
        form.event_type_id = event_type
        return form

    def test_suggested_products_are_proposed(self):
        registry = self._new_list_form(self.baby_shower).save()
        self.assertEqual(registry.line_ids.product_id, self.crib | self.stroller)
        self.assertEqual(registry.line_ids.mapped("qty_wanted"), [1.0, 1.0])

    def test_existing_products_are_kept(self):
        form = self._new_list_form(self.baby_shower)
        # Cambiar de tipo cuando la lista ya tiene productos no los reemplaza
        form.event_type_id = self.wedding
        registry = form.save()
        self.assertEqual(registry.event_type_id, self.wedding)
        self.assertEqual(registry.line_ids.product_id, self.crib | self.stroller)

    def test_type_without_suggestions(self):
        registry = self._new_list_form(self.birthday).save()
        self.assertFalse(registry.line_ids)
