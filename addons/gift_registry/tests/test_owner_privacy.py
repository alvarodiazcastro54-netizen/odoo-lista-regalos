from odoo import fields
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestOwnerPrivacy(TransactionCase):
    """Datos personales del dueño de la lista frente a un vendedor (cajero)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner = cls.env["res.partner"].create({
            "name": "Lucía Ramos", "vat": "45678912",
            "phone": "+51 987 654 321", "email": "lucia.ramos@example.com",
        })
        cls.seller = new_test_user(
            cls.env, login="lr_cajera",
            groups="base.group_user,gift_registry.group_gift_registry_user")
        cls.manager = new_test_user(
            cls.env, login="lr_jefa",
            groups="base.group_user,gift_registry.group_gift_registry_manager")
        cls.gift_list = cls._create_list(cls.owner)

    @classmethod
    def _create_list(cls, owner):
        return cls.env["gift.registry"].create({
            "title": "Baby shower",
            "partner_id": owner.id,
            "event_type_id": cls.env.ref("gift_registry.event_type_baby_shower").id,
            "event_date": fields.Date.today(),
        })

    def test_masked_owner_data(self):
        self.assertEqual(self.gift_list.partner_vat_masked, "••••8912")
        self.assertEqual(self.gift_list.partner_phone_masked, "••••321")
        self.assertEqual(self.gift_list.partner_email_masked, "l•••@example.com")

        # Sin datos no se muestra nada; un dato muy corto no se revela
        bare = self._create_list(self.env["res.partner"].create({"name": "Sin datos", "vat": "123"}))
        self.assertEqual(bare.partner_vat_masked, "••••")
        self.assertFalse(bare.partner_phone_masked)
        self.assertFalse(bare.partner_email_masked)

    def test_owner_link_opens_only_for_managers(self):
        Registry = self.env["gift.registry"]
        seller_form = Registry.with_user(self.seller).get_view(view_type="form")["arch"]
        manager_form = Registry.with_user(self.manager).get_view(view_type="form")["arch"]
        # Cada uno ve el campo del dueño una sola vez; solo el del vendedor no abre la ficha
        self.assertEqual(seller_form.count('name="partner_id"'), 1)
        self.assertEqual(manager_form.count('name="partner_id"'), 1)
        self.assertIn("no_open", seller_form)
        self.assertNotIn("no_open", manager_form)

    def test_search_by_dni_is_exact(self):
        search_view = self.env["gift.registry"].get_view(view_type="search")["arch"]
        # El buscador ya no pasa por la búsqueda de contactos (que mira el DNI de forma parcial)
        self.assertNotIn("child_of", search_view)
        self.assertNotIn('name="partner_id"', search_view)
        self.assertIn("('partner_id.vat', '=', self)", search_view)

        Registry = self.env["gift.registry"].with_user(self.seller)

        def lista(text):  # dominio del campo "Lista" del buscador
            return Registry.search(["|", "|", ("name", "ilike", text), ("title", "ilike", text),
                                    ("partner_id.name", "ilike", text)])

        self.assertEqual(lista("Lucía"), self.gift_list, "Por nombre del dueño sí se encuentra")
        self.assertFalse(lista("45678912"), "El campo general no busca por DNI")
        self.assertEqual(Registry.search([("partner_id.vat", "=", "45678912")]), self.gift_list)
        self.assertFalse(Registry.search([("partner_id.vat", "=", "4567")]), "El DNI parcial no encuentra")
