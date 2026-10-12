from odoo import fields
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon


@tagged("post_install", "-at_install")
class TestGiftRegistryTour(TestPointOfSaleHttpCommon):
    """Prueba de pantalla: necesita un navegador en el servidor de pruebas.

    Con la imagen oficial de Odoo (sin Chrome) esta prueba se omite sola.
    Para ejecutarla de verdad se usa el servicio "odoo-pruebas" de
    docker-compose.pruebas.yml y no se pasa --no-http.
    """

    def test_gift_registry_tour(self):
        product = self.env["product.product"].create({
            "name": "Cafetera de regalo",
            "is_storable": True,
            "available_in_pos": True,
            "list_price": 100.0,
            "taxes_id": False,
        })
        # Stock en el almacén de la caja: sin él, la lista lo mostraría como agotado
        stock_location = self.main_pos_config.picking_type_id.default_location_src_id
        self.env["stock.quant"]._update_available_quantity(product, stock_location, 5)

        owner = self.env["res.partner"].create({"name": "Ana Pérez", "vat": "12345678"})
        gift_list = self.env["gift.registry"].create({
            "name": "LR-TOUR",  # código fijo: el tour lo escribe tal cual
            "title": "Cumpleaños de Ana",
            "partner_id": owner.id,
            "event_type_id": self.env.ref("gift_registry.event_type_birthday").id,
            "event_date": fields.Date.add(fields.Date.today(), days=5),
            "consent_data": True,
            "line_ids": [(0, 0, {"product_id": product.id, "qty_wanted": 2})],
        })
        gift_list.action_activate()

        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour("GiftRegistryTour")

        # Lo que hizo la pantalla quedó registrado en el servidor
        line = gift_list.line_ids
        sold = self.env["pos.order.line"].search([("gift_registry_line_id", "=", line.id)])
        self.assertEqual(len(sold), 1)
        self.assertEqual(sold.order_id.state, "paid")
        self.assertEqual(sold.gift_message, "Con cariño, de la tía Rosa")
        self.assertEqual(line.qty_gifted, 1)
        self.assertEqual(line.status, "partial")
