import posixpath
import re

from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import file_path


@tagged("post_install", "-at_install")
class TestPosThemeStyles(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bundle = cls.env["ir.qweb"]._get_asset_bundle(
            "point_of_sale.assets_prod", css=True, js=False)
        cls.css = cls.bundle.css().raw.decode()

    def test_pos_styles_compile_with_theme(self):
        """Los estilos de la caja compilan con el tema y llevan sus reglas.

        Si una versión nueva de Odoo cambia una variable o un mixin que el tema
        usa, la compilación falla y esta prueba avisa antes de llegar a la caja.
        """
        css = self.css.lower()
        self.assertFalse(self.bundle.css_errors, "Los estilos de la caja no compilan con el tema")
        self.assertNotIn("css error message", css)
        # Variables de marca aplicadas y reglas propias presentes
        self.assertIn('"macromec sans"', css)
        self.assertIn('"macromec mono"', css)
        self.assertIn("#ffb81c", css)
        self.assertIn(".o_gift_registry_dialog", css)

    def test_theme_fonts_exist(self):
        """Cada fuente que el tema referencia existe en el módulo (si no, 404 en la caja)."""
        urls = set(re.findall(r'url\(["\']?([^"\')]*macromec_pos_theme[^"\')]*)', self.css))
        self.assertEqual(len(urls), 4, urls)
        for url in urls:
            # /macromec_pos_theme/static/src/scss/../../fonts/x.ttf -> macromec_pos_theme/static/fonts/x.ttf
            relative = posixpath.normpath(url).lstrip("/")
            self.assertTrue(relative.startswith("macromec_pos_theme/static/fonts/"), url)
            try:
                file_path(relative)
            except FileNotFoundError:
                self.fail(f"El tema referencia una fuente que no existe: {url}")
