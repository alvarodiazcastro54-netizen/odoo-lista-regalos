{
    "name": "Lista de regalos en el Punto de Venta",
    "version": "19.0.1.1.0",
    "category": "Sales/Point of Sale",
    "license": "LGPL-3",
    "author": "Macromec",
    "depends": ["gift_registry", "point_of_sale"],
    "data": [
        "security/gift_registry_pos_security.xml",
        "views/res_config_settings_views.xml",
        "views/gift_registry_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "gift_registry_pos/static/src/**/*",
        ],
    },
    "auto_install": True,
    "installable": True,
}
