import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { registry } from "@web/core/registry";

const dialog = ".o_gift_registry_dialog";

function searchList(text) {
    return [
        {
            content: `escribir "${text}" en el buscador de listas`,
            trigger: `${dialog} .gr-search input`,
            run: `edit ${text}`,
        },
        {
            content: "pulsar Buscar",
            trigger: `${dialog} .gr-search button`,
            run: "click",
        },
    ];
}

// Los datos (lista LR-TOUR de Ana Pérez, DNI 12345678) los crea test_gift_registry_tour.py
registry.category("web_tour.tours").add("GiftRegistryTour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            {
                content: "abrir el diálogo de Lista de regalos",
                trigger: ".control-buttons button:contains('Lista de regalos')",
                run: "click",
            },

            // El DNI parcial no encuentra nada; el DNI exacto, sí
            searchList("1234567"),
            {
                content: "sin resultados con un DNI incompleto",
                trigger: `${dialog} .gr-empty`,
            },
            searchList("12345678"),
            {
                content: "la lista aparece al buscar por DNI exacto",
                trigger: `${dialog} .gr-result:contains('Cumpleaños de Ana')`,
            },

            // Búsqueda por código y entrada a la lista
            searchList("LR-TOUR"),
            {
                content: "la lista aparece por código, con su avance",
                trigger: `${dialog} .gr-result:contains('Cumpleaños de Ana'):contains('0 de 2')`,
                run: "click",
            },
            {
                content: "la cabecera muestra de quién es la lista",
                trigger: `${dialog} .gr-head:contains('Ana Pérez'):contains('LR-TOUR')`,
            },

            // Agregar el regalo, con dedicatoria
            {
                content: "escribir la dedicatoria",
                trigger: `${dialog} #gr_dedication`,
                run: "edit Con cariño, de la tía Rosa",
            },
            {
                content: "agregar el regalo pendiente",
                trigger: `${dialog} .gr-line--pending:contains('Cafetera de regalo') .gr-add`,
                run: "click",
            },
            {
                content: "la línea del ticket lleva la leyenda de la lista",
                trigger:
                    ".product-screen .orderline .gift-registry-info:contains('Regalo para Ana Pérez'):contains('LR-TOUR')",
            },
            {
                content: "y la dedicatoria del invitado",
                trigger:
                    ".product-screen .orderline .gift-registry-message:contains('Con cariño, de la tía Rosa')",
            },

            // Cobro en efectivo
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),

            // El ticket lleva la leyenda
            ReceiptScreen.isShown(),
            {
                content: "leyenda en el ticket",
                trigger:
                    ".receipt-screen .pos-receipt .gift-registry-info:contains('Regalo para Ana Pérez'):contains('LR-TOUR')",
            },
            {
                content: "dedicatoria en el ticket",
                trigger:
                    ".receipt-screen .pos-receipt .gift-registry-message:contains('Con cariño, de la tía Rosa')",
            },
            ReceiptScreen.clickNextOrder(),
        ].flat(),
});
