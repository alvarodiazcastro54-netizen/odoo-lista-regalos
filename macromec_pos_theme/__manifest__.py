{
    "name": "Macromec: tema del Punto de Venta",
    "summary": "Apariencia de la caja: ticket oscuro de alto contraste y botones táctiles grandes",
    "version": "19.0.1.0.0",
    "category": "Sales/Point of Sale",
    "license": "LGPL-3",
    "author": "Macromec",
    "depends": ["point_of_sale", "gift_registry_pos"],
    "assets": {
        "point_of_sale._assets_pos": [
            # Al principio del bundle: fija las variables de marca antes de que
            # Odoo declare las suyas (que usan !default)
            ("prepend", "macromec_pos_theme/static/src/scss/primary_variables.scss"),
            # Al final: reglas propias, después de los estilos de Odoo
            "macromec_pos_theme/static/src/scss/fonts.scss",
            "macromec_pos_theme/static/src/scss/pos_theme.scss",
            "macromec_pos_theme/static/src/scss/gift_registry_dialog.scss",
        ],
    },
    "installable": True,
}
